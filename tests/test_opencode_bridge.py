import asyncio
import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from pc.opencode import Bridge, LEASE_SECONDS, Registry, control, load_discovery


def setUpModule():
    # Never run the developer's real quota command from unit tests.
    global isolated_quota
    isolated_quota = tempfile.TemporaryDirectory()
    patcher = patch("pc.quota.config_path", lambda: Path(isolated_quota.name) / "quota.json")
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)
    unittest.addModuleCleanup(isolated_quota.cleanup)


def message(source="project-a", sequence=1, state="thinking", **fields):
    return dict(v=1, source=source, sequence=sequence, state=state, label="OpenCode active",
                pending_permissions=0, pending_forms=0, active_sessions=1, **fields)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.registry = Registry(lambda: self.now)

    def test_waiting_priority_across_sources(self):
        self.registry.update(message())
        question = message("project-b", state="question")
        question["pending_forms"] = 1
        self.registry.update(question)
        self.assertEqual(self.registry.current()["state"], "question")
        approval = message("project-c", state="permission")
        approval["pending_permissions"] = 2
        self.registry.update(approval)
        self.assertEqual(self.registry.current(), {"state": "permission", "label": "2 approval(s) pending"})

    def test_expired_sources_do_not_keep_an_old_waiting_state(self):
        self.registry.update(message())
        self.now = LEASE_SECONDS
        self.assertIsNone(self.registry.current())

    def test_old_sequence_does_not_refresh_lease(self):
        self.registry.update(message(sequence=2))
        self.now = LEASE_SECONDS - 1
        self.assertFalse(self.registry.update(message(sequence=1)))
        self.now += 1
        self.assertIsNone(self.registry.current())

    def test_bad_labels_counts_and_states_are_rejected(self):
        for fields in ({"label": "x" * 25}, {"label": "line\nbreak"},
                       {"pending_forms": True}, {"state": "hid_arm"}, {"sequence": -1}):
            value = message()
            value.update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.registry.update(value)


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "bridge.json"
        self.bridge = Bridge(port=0, no_ble=True, path=self.path, mute=True, no_notifications=True)
        await self.bridge.start()

    async def asyncTearDown(self):
        await self.bridge.close()
        self.directory.cleanup()

    async def request(self, method="POST", path="/state", body=None, token=None, extra=""):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.bridge.port)
        data = json.dumps(message() if body is None else body).encode()
        authorization = self.bridge.token if token is None else token
        headers = (f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.bridge.port}\r\n"
                   f"Authorization: Bearer {authorization}\r\nContent-Type: application/json\r\n"
                   f"Content-Length: {len(data)}\r\n{extra}\r\n").encode()
        writer.write(headers + data)
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        head, content = response.split(b"\r\n\r\n", 1)
        headers = head.decode("ascii").lower()
        value = json.loads(content) if "content-type: application/json" in headers else content.decode("utf-8")
        return int(head.split(b" ")[1]), value

    async def test_authenticated_state_and_health(self):
        status, response = await self.request()
        self.assertEqual((status, response), (200, {"accepted": True}))
        status, health = await self.request("GET", "/health")
        self.assertEqual(health["state"]["state"], "thinking")
        self.assertTrue(health["read_only"])

    async def test_dashboard_is_same_origin_and_has_manual_controls(self):
        status, page = await self.request("GET", "/", extra="Origin: http://127.0.0.1:%d\r\n" % self.bridge.port)
        self.assertEqual(status, 200)
        self.assertIn("/manual-state", page)
        self.assertIn('value="15"', page)

    async def test_manual_state_temporarily_overrides_and_returns_to_opencode(self):
        self.bridge.usb_connected = True
        self.bridge.registry.update(message(state="working"))
        status, response = await self.request(path="/manual-state",
                                              body={"state": "success", "duration": 15, "label": "Preview"})
        self.assertEqual(status, 200)
        self.assertEqual(response, {"state": "success", "label": "Preview", "duration": 15})
        health = (await self.request("GET", "/health"))[1]
        self.assertEqual(health["state"]["state"], "working")
        self.assertEqual(health["display_state"]["state"], "success")
        self.bridge.manual_override["expires_at"] = time.monotonic() - 1
        health = self.bridge.health()
        self.assertIsNone(health["manual_override"])
        self.assertEqual(health["display_state"]["state"], "working")

    async def test_manual_state_requires_connected_device_and_valid_duration(self):
        status, _ = await self.request(path="/manual-state", body={"state": "success", "duration": 15})
        self.assertEqual(status, 409)
        self.bridge.usb_connected = True
        for duration in (0, 3601, True):
            status, _ = await self.request(path="/manual-state",
                                           body={"state": "success", "duration": duration})
            self.assertEqual(status, 400)
        self.assertIsNone(self.bridge.manual_override)

    async def test_pet_install_requires_sd_and_usb(self):
        status, response = await self.request("POST", "/pets/install", body={"pet": "creepy"})
        self.assertEqual(status, 409)
        self.assertIn("USB", response["error"])

        self.bridge.usb_connected = True
        self.bridge.usb_link = object()
        self.bridge.usb_port = "COM_TEST"
        status, response = await self.request("POST", "/pets/install", body={"pet": "creepy"})
        self.assertEqual(status, 409)
        self.assertIn("SD", response["error"])

    async def test_pet_catalog_lists_only_valid_local_packs(self):
        root = Path(self.directory.name) / "pets"
        (root / "creepy").mkdir(parents=True)
        self.bridge.pet_root = root
        manifest = {"animations": {"idle": {"frames": 5, "bytes": 100}}}
        with patch("pc.opencode.inspect_pack", return_value=("creepy", manifest, ["idle.rgb565"])):
            self.bridge.device_status["pet"] = "creepy"
            status, response = await self.request("GET", "/pets")
        self.assertEqual(status, 200)
        self.assertTrue(response["sd"] is False)
        self.assertEqual(response["pets"], [{"id": "creepy", "name": "Creepy",
                                             "animations": 1, "frames": 5,
                                             "size_bytes": 100, "active": True}])

    async def test_pet_install_pauses_usb_and_runs_local_installer(self):
        class FakeLink:
            def __init__(self, bridge):
                self.bridge = bridge
                self.disconnected = asyncio.Event()
                self.closed = False

            def close(self):
                self.closed = True
                self.bridge.usb_disconnected.set()

        link = FakeLink(self.bridge)
        root = Path(self.directory.name) / "pets"
        (root / "creepy").mkdir(parents=True)
        self.bridge.pet_root = root
        self.bridge.usb_connected = True
        self.bridge.usb_link = link
        self.bridge.usb_port = "COM_TEST"
        self.bridge.usb_disconnected.clear()
        self.bridge.device_status["sd"] = True
        with patch.object(self.bridge, "local_pets", return_value=[{"id": "creepy"}]), \
                patch.object(self.bridge, "_install_local_pet") as installer:
            result = await self.bridge.install_local_pet("creepy")
        self.assertEqual(result, {"installed": "creepy"})
        self.assertTrue(link.disconnected.is_set())
        self.assertTrue(link.closed)
        self.assertTrue(self.bridge.usb_resume.is_set())
        self.assertFalse(self.bridge.pet_installing)
        installer.assert_called_once()

    async def test_pet_activation_uses_same_sd_and_usb_pause(self):
        class FakeLink:
            def __init__(self, bridge):
                self.bridge = bridge
                self.disconnected = asyncio.Event()
                self.closed = False

            def close(self):
                self.closed = True
                self.bridge.usb_disconnected.set()

        link = FakeLink(self.bridge)
        root = Path(self.directory.name) / "pets"
        (root / "creepy").mkdir(parents=True)
        self.bridge.pet_root = root
        self.bridge.usb_connected = True
        self.bridge.usb_link = link
        self.bridge.usb_port = "COM_TEST"
        self.bridge.usb_disconnected.clear()
        self.bridge.device_status["sd"] = True
        self.bridge.local_pets = lambda: [{"id": "creepy"}]
        with patch.object(self.bridge, "_activate_local_pet") as activator:
            result = await self.bridge.activate_local_pet("creepy")
        self.assertEqual(result, {"activated": "creepy"})
        self.assertTrue(link.closed)
        self.assertTrue(self.bridge.usb_disconnected.is_set())
        self.assertTrue(self.bridge.usb_resume.is_set())
        activator.assert_called_once()

    async def test_pet_preview_returns_validated_idle_rgb565_frame(self):
        root = Path(self.directory.name) / "pets"
        folder = root / "creepy"
        folder.mkdir(parents=True)
        frames = bytes(range(32))
        (folder / "idle.rgb565").write_bytes(frames)
        manifest = {"id": "creepy", "format": "RGB565-BE", "width": 2, "height": 4,
                    "states": {"idle": "idle"},
                    "animations": {"idle": {"file": "idle.rgb565", "frames": 2,
                                              "frame_ms": 260, "bytes": 32}}}
        self.bridge.pet_root = root
        with patch("pc.opencode.inspect_pack", return_value=("creepy", manifest, ["idle.rgb565"])):
            preview = self.bridge.local_pet_preview("creepy")
        self.assertEqual((preview["width"], preview["height"]), (2, 4))
        self.assertEqual(preview["frame_ms"], 260)
        self.assertEqual([base64.b64decode(frame) for frame in preview["frames"]],
                         [frames[:16], frames[16:]])

    async def test_unauthorized_and_browser_origin_are_rejected(self):
        self.assertEqual((await self.request(token="wrong"))[0], 401)
        self.assertEqual((await self.request(extra="Origin: https://example.com\r\n"))[0], 403)
        self.assertIsNone(self.bridge.registry.current())

    async def test_non_state_commands_cannot_be_forwarded(self):
        self.assertEqual((await self.request(body={"cmd": "hid_arm"}))[0], 400)
        self.assertIsNone(self.bridge.registry.current())

    async def test_stop_only_stops_the_bridge(self):
        self.assertEqual((await self.request("POST", "/stop"))[0], 200)
        self.assertTrue(self.bridge.stopped.is_set())

    async def test_second_bridge_cannot_replace_live_discovery(self):
        original = load_discovery(self.path)
        second = Bridge(port=0, no_ble=True, path=self.path, mute=True, no_notifications=True)
        with self.assertRaises(ValueError):
            await second.start()
        await second.close()
        self.assertEqual(load_discovery(self.path), original)

    async def test_closing_removes_only_own_discovery(self):
        await self.bridge.close()
        self.assertFalse(self.path.exists())

    async def test_usb_worker_delivers_states_and_reports_connection(self):
        class FakeUsbLink:
            def __init__(self):
                self.requests = []
                self.disconnected = asyncio.Event()
                self.closed = False

            async def request(self, command, **fields):
                self.requests.append((command, fields))

            def close(self):
                self.closed = True

        link = FakeUsbLink()

        async def open_link(port, on_event):
            return link

        bridge = Bridge(port=0, path=Path(self.directory.name) / "usb.json", mute=True,
                        no_notifications=True, serial_port="auto")
        with patch("pc.opencode.find_serial_port", return_value="COM6"), \
                patch("pc.opencode.UsbLink.open", open_link):
            await bridge.start()
            try:
                bridge.registry.update(message(state="working"))
                for _ in range(40):
                    if bridge.last_delivered:
                        break
                    await asyncio.sleep(0.05)
                self.assertEqual(bridge.last_delivered["state"], "working")
                self.assertEqual(link.requests[0], ("status", {}))
                self.assertTrue(bridge.health()["usb_connected"])
                self.assertFalse(bridge.health()["ble_connected"])
            finally:
                await bridge.close()
        self.assertFalse(bridge.health()["usb_connected"])
        self.assertTrue(link.closed)

    async def test_quota_text_is_delivered_with_the_state_and_updates_it(self):
        class FakeLink:
            def __init__(self):
                self.requests = []
                self.disconnected = asyncio.Event()

            async def request(self, command, **fields):
                self.requests.append((command, fields))

        bridge = Bridge(port=0, path=Path(self.directory.name) / "quota.json", mute=True,
                        no_notifications=True, no_ble=True)
        link = FakeLink()
        bridge.registry.update(message(state="working"))
        task = asyncio.create_task(bridge.deliver_states(link))
        try:
            await asyncio.sleep(0.4)
            self.assertNotIn("info", link.requests[0][1])
            bridge.quota.text = "0 / 200"
            await asyncio.sleep(0.4)
            self.assertEqual(link.requests[-1][1]["info"], "0 / 200")
            self.assertEqual(bridge.health()["quota"], "0 / 200")
        finally:
            link.disconnected.set()
            await task

    async def test_control_ignores_environment_proxies_for_loopback(self):
        with patch.dict("os.environ", {"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1", "no_proxy": "", "NO_PROXY": ""}):
            health = await asyncio.to_thread(control, self.path, "health")
        self.assertTrue(health["read_only"])


class CommandLineTests(unittest.TestCase):
    def test_status_and_stop_explain_that_no_bridge_is_running(self):
        from pc import opencode

        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "bridge.json"
            for command in ("status", "stop"):
                with self.subTest(command=command), \
                        patch.object(opencode, "discovery_path", return_value=missing), \
                        patch("sys.argv", ["pc.opencode", command]), \
                        patch("sys.stderr") as stderr, \
                        self.assertRaises(SystemExit) as raised:
                    opencode.main()
                self.assertEqual(raised.exception.code, 1)
                written = "".join(call.args[0] for call in stderr.write.call_args_list)
                self.assertIn("No OpenBuddy bridge is running", written)
