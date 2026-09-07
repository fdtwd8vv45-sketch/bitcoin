from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_state import load_or_create_session, reject_secrets
from local_cli import route_query
from local_notes import recall_notes, remember_note


class LocalCliTests(unittest.TestCase):
    def test_lookup_question(self) -> None:
        text = route_query("What does getblockcount do?")
        self.assertIn("RPC: getblockcount", text)

    def test_rpc_command(self) -> None:
        text = route_query("rpc sendtoaddress")
        self.assertIn("RPC: sendtoaddress", text)

    def test_howto_build(self) -> None:
        text = route_query("how do I build bitcoin core")
        self.assertIn("cmake", text.lower())

    def test_help(self) -> None:
        text = route_query("help")
        self.assertIn("rpc <name>", text)
        self.assertIn("wallet", text)

    def test_unknown_falls_back_to_docs(self) -> None:
        text = route_query("JSON-RPC endpoints")
        self.assertIn("doc/", text)


class LocalNotesAndSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.home = Path(self._tmpdir.name)
        self._env = patch.dict(os.environ, {"BITCOIN_AGENT_HOME": str(self.home)})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_remember_and_recall(self) -> None:
        self.assertIn("Saved note", remember_note("I work on Bitcoin Core RPC tests"))
        text = recall_notes("rpc")
        self.assertIn("Bitcoin Core RPC tests", text)

    def test_rejects_secrets(self) -> None:
        self.assertIsNotNone(reject_secrets("here is my seed phrase apple"))
        self.assertIn("Refusing", remember_note("my private key is hunter2"))
        self.assertIn("No local notes", recall_notes())

    def test_session_reused_until_new(self) -> None:
        first = load_or_create_session(user_id="alice")
        second = load_or_create_session()
        self.assertEqual(first["sessionId"], second["sessionId"])
        self.assertEqual(second["userId"], "alice")
        self.assertGreaterEqual(len(first["sessionId"]), 33)
        third = load_or_create_session(new_session=True, user_id="alice")
        self.assertNotEqual(first["sessionId"], third["sessionId"])


if __name__ == "__main__":
    unittest.main()
