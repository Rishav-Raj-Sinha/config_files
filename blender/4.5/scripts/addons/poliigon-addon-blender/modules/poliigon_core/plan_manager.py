# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import html

from typing import Any, Dict, List, Optional

from .notifications import Notification, ActionType
from .api import STR_NO_PLAN

SIGNAL_PLAN_SUBSCRIBE_EDU = "PLAN_SUBSCRIBE_EDU"
SIGNAL_PLAN_SUBSCRIBE = "PLAN_SUBSCRIBE"
SIGNAL_PLAN_UPGRADE_NO_DLS = "PLAN_UPGRADE_NO_DLS"
SIGNAL_PLAN_PROMPT_UNLIMITED = "PLAN_PROMPT_UNLIMITED"
SIGNAL_PLAN_RESUME_PAUSED = "PLAN_RESUME_PAUSED"
SIGNAL_PLAN_RESUME_CANCELLATION = "PLAN_RESUME_SCHEDULED_CANCEL"
SIGNAL_PLAN_RESUME_SCHEDULED_PAUSE = "PLAN_RESUME_SCHEDULED_PAUSE"


class SubscriptionState(Enum):
    """Values for allowed user subscription states."""
    NOT_POPULATED = 0
    FREE = 1,
    ACTIVE = 2,
    PAUSED = 3,
    PAUSE_SCHEDULED = 4,
    CANCELLED = 4


class PlanUpgradeStatus(Enum):
    NOT_POPULATED = 0
    STUDENT_DISCOUNT = 1
    TEACHER_DISCOUNT = 2
    BECOME_PRO = 3
    UPGRADE_PLAN_BALANCE = 4
    RESUME_PLAN = 5
    REMOVE_SCHEDULED_PAUSE = 6
    REMOVE_CANCELLATION = 7
    UPGRADE_PLAN_UNLIMITED = 8
    NO_UPGRADE_AVAILABLE = 9

    def get_signal_string(self) -> Optional[str]:
        if self == self.NOT_POPULATED:
            return None
        elif self in [self.STUDENT_DISCOUNT, self.TEACHER_DISCOUNT]:
            return SIGNAL_PLAN_SUBSCRIBE_EDU
        elif self == self.BECOME_PRO:
            return SIGNAL_PLAN_SUBSCRIBE
        elif self == self.UPGRADE_PLAN_BALANCE:
            return SIGNAL_PLAN_UPGRADE_NO_DLS
        elif self == self.RESUME_PLAN:
            return SIGNAL_PLAN_RESUME_PAUSED
        elif self == self.REMOVE_SCHEDULED_PAUSE:
            return SIGNAL_PLAN_RESUME_SCHEDULED_PAUSE
        elif self == self.REMOVE_CANCELLATION:
            return SIGNAL_PLAN_RESUME_CANCELLATION
        elif self == self.UPGRADE_PLAN_UNLIMITED:
            return SIGNAL_PLAN_PROMPT_UNLIMITED
        else:
            return None


def _decode_currency_symbol(currency_str: str) -> str:
    decoded_str = ""
    chars = currency_str.split(";")
    for _char in chars:
        # Processing chrs in html format (e.g "82;&#36" => R$)
        try:
            int_char = int(_char)
            _char = chr(int_char)
        except ValueError:
            _char = html.unescape(_char)
        if len(_char) != 1:
            _char = ""
        decoded_str += _char
    return decoded_str


@dataclass
class PoliigonPlanUpgradeInfo:
    ok: bool
    error: Optional[str] = None

    action: Optional[str] = None
    amount_due: Optional[str] = None
    amount_due_renewal: Optional[str] = None
    renewal_date: Optional[str] = None
    tax_rate: Optional[int] = None
    currency_code: Optional[str] = None
    currency_symbol: Optional[str] = None
    previous_assets: Optional[int] = None
    new_assets: Optional[int] = None
    previous_users: Optional[int] = None
    new_users: Optional[int] = None

    @classmethod
    def from_dict(cls, dictionary: Dict):
        new = cls(ok=True)

        new.action = dictionary.get("action")
        new.amount_due = dictionary.get("amount_due")
        new.amount_due_renewal = dictionary.get("amount_due_renewal")
        new.renewal_date = dictionary.get("renewal_date")
        new.tax_rate = dictionary.get("tax_rate")
        new.currency_code = dictionary.get("currency_code")
        new.currency_symbol = _decode_currency_symbol(
            dictionary.get("currency_symbol"))
        new.previous_assets = dictionary.get("previous_assets")
        if isinstance(new.previous_assets, str):
            new.previous_assets = new.previous_assets.title()
        new.new_assets = dictionary.get("new_assets")
        if isinstance(new.new_assets, str):
            new.new_assets = new.new_assets.title()
        new.previous_users = dictionary.get("previous_users")
        new.new_users = dictionary.get("new_users")

        return new


@dataclass
class PoliigonSubscription:
    """Container object for a subscription."""

    plan_name: Optional[str] = None
    plan_credit: Optional[int] = None
    next_credit_renewal_date: Optional[datetime] = None
    current_term_end: Optional[datetime] = None
    next_subscription_renewal_date: Optional[datetime] = None
    plan_paused_at: Optional[datetime] = None
    plan_paused_until: Optional[datetime] = None
    subscription_state: Optional[SubscriptionState] = SubscriptionState.NOT_POPULATED
    period_unit: Optional[str] = None  # e.g. per "month" or "year" for renewing
    plan_price_id: Optional[str] = None
    plan_price: Optional[str] = None  # e.g. "123"
    currency_code: Optional[str] = None  # e.g. "USD"
    base_price: Optional[float] = None  # e.g. 123.45
    currency_symbol: Optional[str] = None  # e.g. "$" (special character)
    is_unlimited: Optional[bool] = None
    is_limited_legacy: Optional[bool] = None
    has_team: Optional[bool] = None

    @staticmethod
    def _to_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None

        # Replacing commas from the string, so they can be formatted as floats.
        # For some users, this value can be formatted as "1,000"
        if isinstance(value, str) and "," in value:
            value.replace(",", "")

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def update_from_upgrade_dict(self, plan_dictionary: Dict) -> Any:  # Returns an instance of the class
        """Creates a class instance from an API V2 available plans
        response plan dictionary."""

        if plan_dictionary.get("name") and plan_dictionary["name"] != STR_NO_PLAN:
            self.plan_name = plan_dictionary["name"]
            self.plan_credit = plan_dictionary.get("meta", {}).get("credits")

            self.period_unit = plan_dictionary.get("periodUnit", None)
            self.plan_price_id = plan_dictionary.get("id", None)
            self.plan_price = plan_dictionary.get("price", None)

            self.currency_code = plan_dictionary.get("currencyCode", None)
            self.base_price = self._to_float(plan_dictionary.get("basePrice", None))

            self.currency_symbol = _decode_currency_symbol(
                plan_dictionary.get("currency_symbol", ""))

            self.is_unlimited = bool(plan_dictionary.get("meta", {}).get("unlimited"))
            self.has_team = bool(plan_dictionary.get("meta", {}).get("hasTeams"))
        else:
            self.plan_name = None
            self.plan_credit = None
            self.next_subscription_renewal_date = None
            self.next_credit_renewal_date = None
            self.subscription_state = SubscriptionState.FREE
            self.period_unit = None
            self.plan_price_id = None
            self.plan_price = None
            self.currency_code = None
            self.base_price = None
            self.currency_symbol = None

    def update_from_dict(self, plan_dictionary: Dict) -> Any:  # Returns an instance of the class
        """TCreates a class instance from an API V1 Subscription Data (Some API
        V2 still returning with same structure as API V1 - e.g. put_upgrade_plan).
        """

        if plan_dictionary.get("plan_name") and plan_dictionary["plan_name"] != STR_NO_PLAN:
            self.plan_name = plan_dictionary["plan_name"]
            self.plan_credit = plan_dictionary.get("plan_credit", None)

            # Extract "2022-08-19" from "2022-08-19 23:58:37"
            renew = plan_dictionary.get("next_subscription_renewal_date", None)
            try:
                renew = datetime.strptime(renew, "%Y-%m-%d %H:%M:%S")
                self.next_subscription_renewal_date = renew
            except (ValueError, TypeError):
                self.next_subscription_renewal_date = None

            end_plan = plan_dictionary.get("current_term_end", None)
            try:
                end_plan = datetime.strptime(end_plan, "%Y-%m-%d %H:%M:%S")
                self.current_term_end = end_plan
            except (ValueError, TypeError):
                self.current_term_end = None

            next_credits = plan_dictionary.get("next_credit_renewal_date", None)
            try:
                next_credits = datetime.strptime(
                    next_credits, "%Y-%m-%d %H:%M:%S")
                self.next_credit_renewal_date = next_credits
            except (ValueError, TypeError):
                self.next_credit_renewal_date = None

            paused_plan_info = plan_dictionary.get("paused_info", None)
            not_renewing = self.next_subscription_renewal_date is None
            if paused_plan_info is not None:
                self.subscription_state = SubscriptionState.PAUSED
                paused_date = paused_plan_info.get("pause_date", None)
                resume_date = paused_plan_info.get("resume_date", None)
                try:
                    self.plan_paused_at = datetime.strptime(
                        paused_date, "%Y-%m-%d %H:%M:%S")
                    self.plan_paused_until = datetime.strptime(
                        resume_date, "%Y-%m-%d %H:%M:%S")

                    now = datetime.now()
                    if now < self.plan_paused_at or now > self.plan_paused_until:
                        self.subscription_state = SubscriptionState.PAUSE_SCHEDULED
                except (ValueError, TypeError):
                    self.plan_paused_until = None
                    self.plan_paused_at = None
            elif not_renewing:
                self.subscription_state = SubscriptionState.CANCELLED
            else:
                self.plan_paused_until = None
                self.plan_paused_at = None
                self.subscription_state = SubscriptionState.ACTIVE

            self.period_unit = plan_dictionary.get("period_unit", None)
            self.plan_price_id = plan_dictionary.get("plan_price_id", None)

            self.plan_price = plan_dictionary.get("plan_price", None)
            self.currency_code = plan_dictionary.get("currency_code", None)

            self.base_price = self._to_float(plan_dictionary.get("base_price", None))
            self.currency_symbol = _decode_currency_symbol(
                plan_dictionary.get("currency_symbol", ""))

            unlimited = plan_dictionary.get("unlimited", None)
            if unlimited is not None:
                self.is_unlimited = bool(unlimited)

            legacy = plan_dictionary.get("limited_legacy", None)
            if legacy is not None:
                self.is_limited_legacy = bool(legacy)

            has_team = bool(plan_dictionary.get("team_id", None))
            if has_team is not None:
                self.has_team = bool(has_team)
        else:
            self.plan_name = None
            self.plan_credit = None
            self.next_subscription_renewal_date = None
            self.next_credit_renewal_date = None
            self.subscription_state = SubscriptionState.FREE
            self.period_unit = None
            self.plan_price_id = None
            self.plan_price = None
            self.currency_code = None
            self.base_price = None
            self.currency_symbol = None


class PoliigonPlanUpgradeManager:
    available_plans: List[Any]  # List[PoliigonSubscription]
    upgrade_plan: Optional[Any] = None  # Optional[PoliigonSubscription]
    status: Optional[PlanUpgradeStatus] = PlanUpgradeStatus.NOT_POPULATED

    upgrade_info: Optional[PoliigonPlanUpgradeInfo] = None
    show_banner: bool = False
    upgrade_dismissed: bool = False
    banner_status_emitted: Optional[PlanUpgradeStatus] = None

    # Upgrade banner and popups content to be used on DCC UI;
    content: Optional[Any] = None  # UpgradeContent (Circular Import)

    def __init__(self,
                 addon: Any  # PoliigonAddon
                 ):
        self.addon = addon
        self.user = self.addon.user
        self.available_plans = []
        self.set_upgrade_status()

    def refresh(self,
                plans_info: Optional[Dict] = None,
                only_resume_popup: bool = False,
                clean_plans: bool = False
                ) -> None:
        self.user = self.addon.user
        if clean_plans:
            self.available_plans = []
        if plans_info is not None:
            self.set_available_plans(plans_info)
        self.set_upgrade_plan()
        self.set_upgrade_status()
        self.set_show_banner()
        if self.content is not None:
            self.content.refresh(self, only_resume_popup)

    def get_last_dismiss(self) -> Optional[datetime]:
        last_dismiss = self.addon.settings_config.get(
            "upgrade", "last_dismiss", fallback=None)
        if last_dismiss is None:
            return None
        return datetime.strptime(last_dismiss, "%Y-%m-%d %H:%M:%S")

    def check_last_dismiss_interval(self, day_interval: int = 7) -> bool:
        last_dismiss = self.get_last_dismiss()
        if last_dismiss is None:
            return True

        diff = datetime.now() - last_dismiss
        if diff.days >= day_interval:
            return True
        return False

    def set_show_banner(self) -> None:
        if self.user is None:
            return
        if self.addon.user.credits is None:
            return
        upgrade_available = None not in [self.upgrade_info, self.upgrade_plan]
        if self.status in [PlanUpgradeStatus.NOT_POPULATED,
                           PlanUpgradeStatus.NO_UPGRADE_AVAILABLE]:
            self.show_banner = False
        elif self.status in [PlanUpgradeStatus.STUDENT_DISCOUNT,
                             PlanUpgradeStatus.TEACHER_DISCOUNT,
                             PlanUpgradeStatus.BECOME_PRO,
                             PlanUpgradeStatus.RESUME_PLAN,
                             PlanUpgradeStatus.REMOVE_SCHEDULED_PAUSE,
                             PlanUpgradeStatus.REMOVE_CANCELLATION]:
            self.show_banner = True
        elif self.status == PlanUpgradeStatus.UPGRADE_PLAN_BALANCE:
            self.show_banner = upgrade_available
        elif self.status == PlanUpgradeStatus.UPGRADE_PLAN_UNLIMITED:
            if self.addon.user.plan.plan_credit is None or not self.check_last_dismiss_interval():
                self.show_banner = False
            else:
                self.show_banner = upgrade_available
        else:
            self.show_banner = False

    def emit_signal(self,
                    view: bool = False,
                    dismiss: bool = False,
                    clicked: bool = False) -> None:
        if self.status is None:
            return

        signal_str = self.status.get_signal_string()

        if signal_str is None:
            return

        action_type = ActionType.OPEN_URL
        if self.content is not None and self.content.open_popup:
            action_type = ActionType.POPUP_MESSAGE

        # Mocked Notification to be used for signals
        signal_notice = Notification(id_notice=signal_str,
                                     title=self.status.name,
                                     priority=0,
                                     label=self.status.name)
        signal_notice.action = action_type

        if dismiss and not self.upgrade_dismissed:
            self.addon.notify._signal_dismiss(signal_notice)
        elif view:
            self.addon.notify._signal_view(signal_notice)
        elif clicked:
            self.addon.notify._signal_clicked(signal_notice)

    def check_show_banner(self) -> bool:
        # Checks if the wm onboarding banner is drawn or not
        if not self.addon.is_onboarding_wm_preview_done():
            return False

        if self.user is None:
            return False
        do_show_banner = self.show_banner

        # Checks if the status changed since the last view signal
        different_emit_signal_status = self.banner_status_emitted != self.status
        if do_show_banner and different_emit_signal_status:
            self.emit_signal(view=True)
            self.banner_status_emitted = self.status

        return do_show_banner

    def dismiss_upgrade(self) -> None:
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.addon.settings_config.set(
            "upgrade", "last_dismiss", date_now)
        self.set_show_banner()
        self.addon._settings.save_settings()
        self.emit_signal(dismiss=True)
        self.upgrade_dismissed = True

    def set_upgrade_status(self) -> None:
        if self.user is None:
            return
        if self.user.credits is None:
            return
        subscription_state = self.user.plan.subscription_state
        if subscription_state == SubscriptionState.FREE:
            if self.user.is_student:
                self.status = PlanUpgradeStatus.STUDENT_DISCOUNT
            elif self.user.is_teacher:
                self.status = PlanUpgradeStatus.TEACHER_DISCOUNT
            else:
                self.status = PlanUpgradeStatus.BECOME_PRO
        elif subscription_state == SubscriptionState.PAUSED:
            self.status = PlanUpgradeStatus.RESUME_PLAN
        elif subscription_state == SubscriptionState.PAUSE_SCHEDULED:
            self.status = PlanUpgradeStatus.REMOVE_SCHEDULED_PAUSE
        elif subscription_state == SubscriptionState.CANCELLED:
            self.status = PlanUpgradeStatus.REMOVE_CANCELLATION
        elif subscription_state == SubscriptionState.ACTIVE:
            if self.upgrade_plan is None:
                self.status = PlanUpgradeStatus.NO_UPGRADE_AVAILABLE
            elif self.user.credits == 0:
                self.status = PlanUpgradeStatus.UPGRADE_PLAN_BALANCE
            elif self.upgrade_plan.is_unlimited:
                self.status = PlanUpgradeStatus.UPGRADE_PLAN_UNLIMITED
            else:
                self.status = PlanUpgradeStatus.NO_UPGRADE_AVAILABLE
        else:
            self.status = PlanUpgradeStatus.NO_UPGRADE_AVAILABLE

    def set_available_plans(self, plans_dict: Dict) -> None:
        yearly_plans = plans_dict.get("plan_year", [])
        monthly_plans = plans_dict.get("plan_month", [])

        # Clean available plans before populating again
        self.available_plans = []

        for _plan in (yearly_plans + monthly_plans):
            plan_data = PoliigonSubscription()
            plan_data.update_from_upgrade_dict(_plan)
            self.available_plans.append(plan_data)

    def set_upgrade_plan(self) -> None:
        """Method to define what is the next plan to offer to the user.

        We have two main scenarios for upgrading:
        Upgrade to Pro Plan: If a given user has a next Pro plan available and
        (only if) their credits are empty, we offer the next pro plan
        (not dismissible);

        Upgrade to Unlimited:
        For any Pro plan user that credits are more than zero, we should show
        the Upgrade to Unlimited banner (this one is dismissible);"""

        if self.user is None or len(self.available_plans) == 0:
            return

        if self.user.plan.is_unlimited:
            # The only benefit to upgrade is to get more downloads, if you're
            # already unlimited, there's nothing to upgrade to
            self.upgrade_plan = None
            return

        if self.user.plan.has_team:
            # Let's not offer updates to team members, since these contracts
            # are handled separately
            self.upgrade_plan = None
            return

        upgrade_pro_plan = None
        upgrade_unlimited_plan = None
        filter_period_unit = [_plan for _plan in self.available_plans
                              if _plan.period_unit == self.user.plan.period_unit]

        filter_has_team = [_plan for _plan in filter_period_unit
                           if _plan.has_team == self.user.plan.has_team]

        sorted_price_plans = sorted(filter_has_team, key=lambda plan: plan.plan_credit)
        for _plan in sorted_price_plans:
            if self.user.plan.is_unlimited and not _plan.is_unlimited:
                # Don't offer credit-based plans if they are already unlimited
                continue

            if self.user.plan.plan_credit >= _plan.plan_credit and not _plan.is_unlimited:
                # Don't offer plans which have the same or fewer credits
                continue

            if _plan.is_unlimited and upgrade_unlimited_plan is None:
                upgrade_unlimited_plan = _plan
            if upgrade_pro_plan is None:
                upgrade_pro_plan = _plan
            if None not in [upgrade_unlimited_plan, upgrade_pro_plan]:
                break

        if upgrade_pro_plan is None and upgrade_unlimited_plan is None:
            self.upgrade_plan = None
        elif self.user.credits == 0 and upgrade_pro_plan is not None:
            self.upgrade_plan = upgrade_pro_plan
        else:
            self.upgrade_plan = upgrade_unlimited_plan

    def finish_upgrade_plan(self) -> None:
        """This method should be called to confirm an update, resume or
        choosing plan in the addon dcc side"""
        if self.addon.api_rc is None:
            self.addon.logger.error("API RC not defined")
            return

        choose_plans_status = [PlanUpgradeStatus.STUDENT_DISCOUNT,
                               PlanUpgradeStatus.TEACHER_DISCOUNT,
                               PlanUpgradeStatus.BECOME_PRO]

        resume_status = [PlanUpgradeStatus.RESUME_PLAN,
                         PlanUpgradeStatus.REMOVE_SCHEDULED_PAUSE,
                         PlanUpgradeStatus.REMOVE_CANCELLATION]

        upgrade_status = [PlanUpgradeStatus.UPGRADE_PLAN_BALANCE,
                          PlanUpgradeStatus.UPGRADE_PLAN_UNLIMITED]

        if self.status in choose_plans_status:
            self.addon._api.open_poliigon_link("subscribe")
        elif self.status in resume_status:
            callback = self.addon.api_rc._addon_params.callback_resume_plan
            self.addon.api_rc.add_job_resume_plan(callback_done=callback)
        elif self.status in upgrade_status:
            callback = self.addon.api_rc._addon_params.callback_put_upgrade_plan
            self.addon.api_rc.add_job_put_upgrade_plan(callback_done=callback)
        else:
            self.addon.logger.error(
                f"Current user not available for upgrade: {self.user}")
