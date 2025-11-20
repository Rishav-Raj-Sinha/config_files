from typing import List, Callable
import gettext


def _m(message: str) -> str:
    """Placeholder to mark strings to be translated and stored on .pot file"""
    return message


def _o(message: str) -> str:
    """Gets the original string, e.g after set a translated variable"""
    return gettext.dgettext("en-US", message)


def _t(message: str) -> str:
    """Gets the translated string with the current domain setup"""
    try:
        return gettext.gettext(message)  # noqa
    except NameError:
        # If none domain is initialized, _() will not be defined yet;
        return message


class MsgFallback(gettext.NullTranslations):
    """Fallback to report if one is trying to translate a message that is not
    registered on the stored domains (platforms and languages);
    """

    def __init__(self, fallback_method: Callable = None) -> None:
        super().__init__()
        self.fallback = fallback_method

    def gettext(self, msg) -> str:
        self.fallback(msg)
        return msg


class Multilingual:
    """Class to store and manage all the domains for multilingual translation."""

    report_message: Callable  # Report function to be set on the addon;
    curr_language: str
    supported_languages = ["en-US", "test_dummy"]

    # All domains already registered.
    # NOTE: Do not change this from outside this module;
    _domains: List[gettext.GNUTranslations]

    def __init__(self):
        self._domains = []
        self.report_message = None
        self.curr_language = None

    def install_domain(self,
                       language: str,
                       dir_lang: str,
                       domain: str = "addon-core") -> None:

        if language not in self.supported_languages:
            return

        current_domain = gettext.translation(domain,
                                             localedir=dir_lang,
                                             languages=[language, "en-US"])
        current_domain.install()

        # If there are already installed domains, they are used as fallback if
        # a given message is not found. Each new domain will fall back to the
        # previous one - until the first added domain, which will call
        # report_message_missing;
        if len(self._domains) > 0:
            current_domain.add_fallback(self._domains[-1])
        else:
            current_domain.add_fallback(MsgFallback(self.report_message_missing))

        self.curr_language = language
        self._domains.append(current_domain)

    def report_message_missing(self, msg: str) -> None:
        if self.report_message is not None and self.curr_language != "en-US":
            error_msg = f"{self.curr_language}:\"{msg}\""
            self.report_message("missing_locale_msg", error_msg, "error")
