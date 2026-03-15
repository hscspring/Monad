import unittest
from monad.tools.web_fetch import run


class TestWebFetchExplicitModes(unittest.TestCase):
    """Test each mode explicitly."""

    def test_fast_mode(self):
        result = run(url='https://httpbin.org/html', mode='fast', timeout=10)
        self.assertIn("Herman Melville", result)

    def test_fast_mode_selector(self):
        result = run(url='https://httpbin.org/html', mode='fast', selector='h1', timeout=10)
        self.assertIn("Herman Melville - Moby-Dick", result)

    def test_stealth_mode(self):
        result = run(url='https://httpbin.org/html', mode='stealth', timeout=15)
        self.assertIn("Herman Melville", result)

    def test_browser_mode(self):
        result = run(url='https://www.baidu.com', mode='browser', timeout=15)
        self.assertIn("百度", result)

    def test_browser_mode_selector(self):
        result = run(url='https://www.baidu.com', mode='browser', selector='title', timeout=15)
        self.assertIn("百度", result)


class TestWebFetchAutoMode(unittest.TestCase):
    """Test default auto mode (smart fallback)."""

    def test_auto_simple_page(self):
        """Auto mode should fetch simple pages quickly via fast."""
        result = run(url='https://httpbin.org/html', timeout=10)
        self.assertIn("Herman Melville", result)

    def test_auto_default_mode(self):
        """Default mode should be auto."""
        result = run(url='https://httpbin.org/html', timeout=10)
        self.assertIn("Herman Melville", result)


class TestWebFetchErrorHandling(unittest.TestCase):
    """Test error handling."""

    def test_missing_url(self):
        result = run(url='')
        self.assertIn("Error: No URL provided.", result)

    def test_invalid_mode(self):
        result = run(url='https://example.com', mode='invalid')
        self.assertIn("Invalid mode", result)

    def test_bad_url(self):
        """Should not crash on bad URLs."""
        result = run(url='https://this-domain-does-not-exist-12345.com', mode='fast', timeout=5)
        self.assertIsInstance(result, str)
        # Should return an error message, not crash
        self.assertTrue(len(result) > 0)


if __name__ == '__main__':
    unittest.main()
