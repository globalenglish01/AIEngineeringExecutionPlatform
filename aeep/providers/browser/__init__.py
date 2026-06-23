"""Browser Provider package.

WARNING: This is the ONLY package where `import playwright` is allowed.
Do NOT import from this package in core/, workflow/, agents/, or validation/.
"""

from aeep.providers.browser.browser_provider import BrowserProvider
from aeep.providers.browser.session import BrowserConfig, BrowserSession

__all__ = ["BrowserConfig", "BrowserProvider", "BrowserSession"]
