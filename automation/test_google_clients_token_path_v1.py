import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import google_clients


class TokenPathTests(unittest.TestCase):
    def test_explicit_missing_path_is_not_silently_replaced(self):
        with self.assertRaises(google_clients.GoogleCredentialError) as caught:
            google_clients.load_credentials(token_path=Path('/definitely/missing/token.json'), persist_refresh=False)
        self.assertEqual(caught.exception.code, 'GOOGLE_OAUTH_TOKEN_MISSING')

    def test_explicit_path_is_used_and_refresh_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / 'token.json'; token.write_text('{"token":"x"}')
            original = token.read_bytes()
            class FakeCredentials:
                valid = False; expired = True; refresh_token = 'r'; scopes = google_clients.SCOPES
                def refresh(self, request): self.valid = True
            with patch.object(google_clients.Credentials, 'from_authorized_user_file', return_value=FakeCredentials()):
                result = google_clients.load_credentials(token_path=token, persist_refresh=False)
            self.assertTrue(result.valid)
            self.assertEqual(token.read_bytes(), original)


if __name__ == '__main__': unittest.main()
