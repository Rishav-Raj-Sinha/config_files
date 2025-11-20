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

from typing import Any, Dict, Optional, Tuple

from .plan_manager import (PoliigonPlanUpgradeManager,
                           PlanUpgradeStatus,
                           PoliigonSubscription)
from .multilingual import _t


@dataclass
class UpgradeIcons:
    check: str
    info: str
    unlimited: str


class UpgradeContent:
    """Class to be created in the DCC side which will define and store all
    UI content information."""

    upgrade_manager: PoliigonPlanUpgradeManager
    current_plan: PoliigonSubscription

    banner_primary_text: str = ""
    banner_secondary_text: str = ""
    banner_button_text: str = ""
    allow_dismiss: bool = False
    open_popup: bool = False
    icon_path: Optional[str] = None

    # For upgrade popup
    upgrade_popup_title: Optional[str] = None
    upgrade_popup_table: Optional[Dict[str, str]] = None
    upgrade_popup_key_value: Optional[Dict[str, str]] = None
    upgrade_popup_text: Optional[str] = None
    upgrade_popup_confirm_button: Optional[str] = None
    upgrade_popup_pricing_button: Optional[str] = None
    upgrade_popup_terms_button: Optional[str] = None

    # Upgrading process messages
    upgrading_primary_text: Optional[str] = None
    upgrading_secondary_text: Optional[str] = None

    # For success popups
    success_popup_title: Optional[str] = None
    success_popup_text: Optional[str] = None

    # For error popups
    error_popup_title: Optional[str] = None
    error_popup_text: Optional[str] = None

    # Flags to be used for P4B UI
    as_single_paragraph: bool = False

    # Flag to use in P4B & P4C UI
    use_single_policy_link: bool = True

    # Stores the icon paths for each dcc
    icons: Optional[UpgradeIcons] = None

    def __init__(self,
                 upgrade_manager: PoliigonPlanUpgradeManager,
                 as_single_paragraph: bool = False,
                 use_single_policy_link: bool = True,
                 icons: Optional[Tuple[str, str, str]] = None):
        """Class to handle all the Content for Upgrade UI in each DCC.

        Parameters:
        upgrade_manager: addon.upgrade_manager instance of PoliigonPlanUpgradeManager;
        as_single_paragraph: If True, the banner_secondary_text will be set as
                             None, and all the text will be represented as
                             a single paragraph in banner_primary_text;
        icons: The icon paths to be used in upgrade manager (order: check, info, unlimited)

        NOTE: This class instance should be created in the addon side and
              stored in addon.upgrade_manager.content;
        """

        self.as_single_paragraph = as_single_paragraph
        self.use_single_policy_link = use_single_policy_link
        if icons is not None:
            # Icon paths order: check, info, unlimited
            self.icons = UpgradeIcons(icons[0], icons[1], icons[2])

        self.refresh(upgrade_manager)

    def refresh(self,
                upgrade_manager: PoliigonPlanUpgradeManager,
                only_resume_popup: bool = False
                ) -> None:
        if upgrade_manager is not None:
            self.upgrade_manager = upgrade_manager
        if self.upgrade_manager is None:
            return
        if self.upgrade_manager.addon.user is None:
            return

        self.current_plan = self.upgrade_manager.addon.user.plan

        if only_resume_popup:
            # When resuming, the renewal date is updated, so in this
            # scenario we use this flag to only update the popup. If populate()
            # was called, now the status would be NO_UPGRADE_AVAILABLE and
            # the popup message will be another
            self.set_resume_success_popup()
            return

        self.populate()

    def student_discount(self, is_teacher: bool = False) -> Any:
        primary = _t("Access the entire library with a Poliigon Plan")
        secondary = _t("{0} can claim a 50% discount".format(
                       _t("Students") if not is_teacher else _t("Teachers")))
        if self.as_single_paragraph:
            self.banner_primary_text = f"{primary}. {secondary}"
            self.banner_secondary_text = None
        else:
            self.banner_primary_text = primary
            self.banner_secondary_text = secondary
        self.banner_button_text = _t("Choose Your Plan")
        self.allow_dismiss = False
        self.open_popup = False
        if self.icons is not None:
            self.icon_path = self.icons.check

    def become_pro(self) -> Any:
        primary = _t("Access the entire library with a Poliigon Plan")
        secondary = _t("Download and import from the entire Poliigon library")
        if self.as_single_paragraph:
            # To keep it slimmer, do just the primary text.
            self.banner_primary_text = f"{primary}"
            self.banner_secondary_text = None
        else:
            self.banner_primary_text = primary
            self.banner_secondary_text = secondary
        self.banner_button_text = _t("Choose Your Plan")
        self.allow_dismiss = False
        self.open_popup = False
        if self.icons is not None:
            self.icon_path = self.icons.check

    def upgrade_balance(self) -> Any:
        primary_text, secondary_text = self._get_upgrade_text_upgrade_balance()

        self.banner_primary_text = primary_text
        self.banner_secondary_text = secondary_text
        self.banner_button_text = _t("Get More Downloads")
        self.allow_dismiss = False
        self.open_popup = True

        if self.icons is not None:
            self.icon_path = self.icons.info

    def resume_plan(self) -> Any:
        primary_text, secondary_text = self._get_upgrade_text_paused_until()

        self.banner_primary_text = primary_text
        self.banner_secondary_text = secondary_text
        self.banner_button_text = _t("Resume Plan")
        self.allow_dismiss = False
        self.open_popup = True

        if self.icons is not None:
            self.icon_path = self.icons.info

    def remove_cancel(self) -> Any:
        primary_text, secondary_text = self._get_upgrade_text_term_end()

        self.banner_primary_text = primary_text
        self.banner_secondary_text = secondary_text
        self.banner_button_text = _t("Resume Plan")
        self.allow_dismiss = False
        self.open_popup = True

        if self.icons is not None:
            self.icon_path = self.icons.info

    def remove_pause(self) -> Any:
        primary_text, secondary_text = self._get_upgrade_text_paused_at()

        self.banner_primary_text = primary_text
        self.banner_secondary_text = secondary_text
        self.banner_button_text = _t("Cancel Pause")
        self.allow_dismiss = False
        self.open_popup = True

        if self.icons is not None:
            self.icon_path = self.icons.info

    def upgrade_unlimited(self) -> Any:
        primary_text, secondary_text = self._get_upgrade_text_unlimited()

        self.banner_primary_text = primary_text
        self.banner_secondary_text = secondary_text
        self.banner_button_text = _t("Upgrade to Unlimited")
        self.allow_dismiss = True
        self.open_popup = True

        if self.icons is not None:
            self.icon_path = self.icons.unlimited
        return self

    def _get_upgrade_text_upgrade_balance(self) -> Tuple[str, Optional[str]]:
        """Returns text to display in case of a scheduled pause subscription."""
        next_renewal_date = self.current_plan.next_subscription_renewal_date
        diff = next_renewal_date - datetime.now()

        head = _t("You’re out of downloads")
        text = _t("You’ll get more in {0} days or upgrade "
                  "to download now").format(diff.days)
        if self.as_single_paragraph:
            return f"{head}. {text}", None
        else:
            return head, text

    def _get_upgrade_text_paused_at(self) -> Tuple[str, Optional[str]]:
        """Returns text to display in case of a scheduled pause subscription."""

        pause_date = self.current_plan.plan_paused_at
        date_paused_until = None
        if pause_date is not None:
            date_paused_until = self.current_plan.plan_paused_at.strftime("%d %b %Y")

        head = _t("Your plan will pause on {0}").format(date_paused_until)
        text = _t("Cancel pause to keep downloading")
        if self.as_single_paragraph:
            return f"{head}. {text}", None
        else:
            return head, text

    def _get_upgrade_text_paused_until(self) -> Tuple[str, Optional[str]]:
        """Returns text to display in case of a paused subscription."""

        date_paused_until = self.current_plan.plan_paused_until.strftime("%d %b %Y")
        head = _t("Your plan is paused until {0}").format(date_paused_until)
        text = _t("Resume your plan to download new assets")
        if self.as_single_paragraph:
            return f"{head}. {text}", None
        else:
            return head, text

    def _get_upgrade_text_term_end(self) -> Tuple[str, Optional[str]]:
        """Returns text to display in case of a cancelled subscription."""

        date_term_end = self.current_plan.current_term_end.strftime("%d %b %Y")
        head = _t("Your plan will end on {0}").format(date_term_end)
        text = _t("Resume your plan to keep downloading")
        if self.as_single_paragraph:
            return f"{head}. {text}", None
        else:
            return head, text

    def _get_upgrade_text_unlimited(self) -> Tuple[str, Optional[str]]:
        """Returns text to display in case of non-unlimited subscription."""

        head = _t("Need more downloads?")
        text = _t("Upgrade to unlimited and never worry about limits again")
        if self.as_single_paragraph:
            # Per Blender design, don't include the second bit of text
            return f"{head}", None
        else:
            return head, text

    def _get_text_price_change(self) -> str:
        price_old = self.current_plan.base_price
        price_new = self.upgrade_manager.upgrade_plan.base_price

        currency_code = self.upgrade_manager.upgrade_info.currency_code
        currency_symbol = self.upgrade_manager.upgrade_info.currency_symbol

        if price_old is not None:
            price_old = f"{currency_symbol}{price_old:.2f} {currency_code}"
        if price_new is not None:
            price_new = f"{currency_symbol}{price_new:.2f} {currency_code}"

        return f"{price_old} \u2192 {price_new}"

    def _get_text_licence(self) -> str:
        """Decodes boolean has_team into 'Team' or 'Individual'."""

        has_team = self.upgrade_manager.upgrade_plan.has_team
        if has_team:
            text_licence = _t("Team")
        else:
            text_licence = _t("Individual")
        return text_licence

    def _get_text_billing_period(self) -> str:
        """Decodes period_unit into 'Yearly' or 'Monthly'."""

        period_unit = self.upgrade_manager.upgrade_plan.period_unit
        if period_unit == "year":
            text_billing = _t("Yearly")
        elif period_unit == "month":
            text_billing = _t("Monthly")
        else:
            text_billing = period_unit
        return text_billing

    def _get_text_assets_change(self) -> str:
        """Returns the change in assets count as string ('previous -> new')."""

        new_assets = self.upgrade_manager.upgrade_info.new_assets
        prev_assets = self.upgrade_manager.upgrade_info.previous_assets
        text_assets = f"{prev_assets} \u2192 {new_assets}"
        return text_assets

    def _get_text_users_change(self) -> str:
        """Returns the change in user count as string ('previous -> new')."""
        new_users = self.upgrade_manager.upgrade_info.new_users
        previous_users = self.upgrade_manager.upgrade_info.previous_users
        text_users = f"{previous_users} \u2192 {new_users}"
        return text_users

    def _get_text_amount_due(self) -> str:
        """Returns amount due as string with currency code and symbol."""

        amount_due = self.upgrade_manager.upgrade_info.amount_due
        currency_code = self.upgrade_manager.upgrade_info.currency_code
        currency_symbol = self.upgrade_manager.upgrade_info.currency_symbol
        text_amount_due = f"{currency_symbol}{amount_due} {currency_code}"
        return text_amount_due

    def _get_text_amount_due_renewal(self) -> str:
        """Returns amount due on renewal as string with
        currency code and symbol.
        """

        amount_due_renewal = self.upgrade_manager.upgrade_info.amount_due_renewal
        currency_code = self.upgrade_manager.upgrade_info.currency_code
        currency_symbol = self.upgrade_manager.upgrade_info.currency_symbol
        text_amount_due_renewal = (f"{currency_symbol}{amount_due_renewal} "
                                   f"{currency_code}")
        return text_amount_due_renewal

    def set_resume_popup_information(self):
        # TODO: Check string phrasing here (Maybe different texts for each one of the scenarios of resuming)
        self.upgrade_popup_text = _t("Would you like to resume your plan? "
                                     "You will be charged for renewal and can "
                                     "start downloading straight away.")
        self.upgrade_popup_title = _t("Resume Plan")
        self.upgrade_popup_confirm_button = _t("Resume Plan")

        self.upgrading_primary_text = _t("Resuming plan...")
        self.upgrading_secondary_text = _t("This may take a few seconds.")
        self.upgrade_popup_table = None
        self.upgrade_popup_key_value = None
        self.upgrade_popup_pricing_button = None
        self.upgrade_popup_terms_button = None

    def set_remove_scheduled_pause_popup_information(self):
        # TODO: Check string phrasing here (Maybe different texts for each one of the scenarios of resuming)
        self.upgrade_popup_text = _t("Would you like to remove the scheduled pause? ")
        self.upgrade_popup_title = _t("Cancel Pause")
        self.upgrade_popup_confirm_button = _t("Cancel Pause")

        self.upgrading_primary_text = _t("Cancelling Pause...")
        self.upgrading_secondary_text = _t("This may take a few seconds.")
        self.upgrade_popup_table = None
        self.upgrade_popup_key_value = None
        self.upgrade_popup_pricing_button = None
        self.upgrade_popup_terms_button = None

    def set_remove_scheduled_cancel_popup_information(self):
        # TODO: Check string phrasing here (Maybe different texts for each one of the scenarios of resuming)
        self.upgrade_popup_text = _t("Would you like to remove the scheduled cancellation?")
        self.upgrade_popup_title = _t("Remove Cancellation")
        self.upgrade_popup_confirm_button = _t("Remove Cancellation")

        self.upgrading_primary_text = _t("Removing Cancellation...")
        self.upgrading_secondary_text = _t("This may take a few seconds.")
        self.upgrade_popup_table = None
        self.upgrade_popup_key_value = None
        self.upgrade_popup_pricing_button = None
        self.upgrade_popup_terms_button = None

    def set_upgrade_popup_information(self):
        self.upgrade_popup_table = {
            _t("Assets per month:"): self._get_text_assets_change(),

            # The following line are commented due to a decision of not showing
            # team related information on confirmation popup;
            # _t("Users:"): self._get_text_users_change(),
            # _t("License:"): self._get_text_licence(),

            _t(f"{self._get_text_billing_period()} price:"): self._get_text_price_change(),
            _t("Starts:"): _t("Today"),
            _t("Billing frequency:"): self._get_text_billing_period(),
            _t("Renewal:"): self.upgrade_manager.upgrade_info.renewal_date
        }

        self.upgrade_popup_key_value = {
            _t("Due today:"): self._get_text_amount_due(),
            _t("Due on renewal:"): self._get_text_amount_due_renewal()
        }

        if self.use_single_policy_link:
            confirm_text = _t("By confirming you agree to our Unlimited Fair Use "
                              "Policy, Terms & Conditions, Privacy & Refund Policy below.")
        else:
            confirm_text = _t("By confirming you agree to our Unlimited Fair Use "
                              "Policy, Terms & Conditions, Privacy & Refund Policy.")

        tax_text = ""
        if self.upgrade_manager.upgrade_info.tax_rate not in [None, 0]:
            tax_text = _t("Due today and renewal prices include {0}% tax. ").format(
                self.upgrade_manager.upgrade_info.tax_rate)
        self.upgrade_popup_text = f"{tax_text}{confirm_text}"

        self.upgrade_popup_title = _t("Change Plan")
        self.upgrade_popup_confirm_button = _t("Confirm Plan Change")
        self.upgrade_popup_pricing_button = _t("View All Pricing")
        self.upgrade_popup_terms_button = _t("Terms & Policy Documents")

    def set_upgrade_success_popup(self):
        self.success_popup_title = _t("Plan Change Successful")
        self.success_popup_text = _t("You have successfully updated your plan.")

        # TODO(Joao): Implement different hard coded error messages for each
        #  scenario - look for strings in the api error (maybe error codes)

        self.error_popup_title = _t("Error Upgrading Plan")
        self.error_popup_text = _t("Upgrade Plan Failed. \n\n{0}\n\n"
                                   "Try again later or reach out to support.")

        self.upgrading_primary_text = _t("Upgrading Plan...")
        self.upgrading_secondary_text = _t("This may take a few seconds.")

    def set_resume_success_popup(self):
        # TODO: Check string phrasing here (Just a mock str for now)
        renewal_date = self.current_plan.next_subscription_renewal_date
        text = _t("Your plan has successfully resumed")
        if renewal_date is not None:
            renewal_text = self.current_plan.next_subscription_renewal_date.strftime("%d %b %Y")
            renewal_date_text = _t("and will renew on {0}").format(renewal_text)
            text = f"{text} {renewal_date_text}"
        else:
            text = f"{text}."

        self.success_popup_title = _t("Plan Resumed")
        self.success_popup_text = text

        self.error_popup_title = _t("Error Resuming Plan")
        self.error_popup_text = _t("Resume Plan Failed. \n\n{0}\n\n"
                                   "Try again later or reach out to support.")

    def populate(self) -> None:
        upgrade_satus = self.upgrade_manager.status
        if upgrade_satus == PlanUpgradeStatus.STUDENT_DISCOUNT:
            self.student_discount()
        if upgrade_satus == PlanUpgradeStatus.TEACHER_DISCOUNT:
            self.student_discount(is_teacher=True)
        elif upgrade_satus == PlanUpgradeStatus.BECOME_PRO:
            self.become_pro()
        elif upgrade_satus == PlanUpgradeStatus.UPGRADE_PLAN_BALANCE:
            self.upgrade_balance()
            if self.upgrade_manager.upgrade_info is None:
                return
            self.set_upgrade_popup_information()
            self.set_upgrade_success_popup()
        elif upgrade_satus == PlanUpgradeStatus.RESUME_PLAN:
            self.resume_plan()
            self.set_resume_popup_information()
            self.set_resume_success_popup()
        elif upgrade_satus == PlanUpgradeStatus.REMOVE_SCHEDULED_PAUSE:
            self.remove_pause()
            self.set_remove_scheduled_pause_popup_information()
            self.set_resume_success_popup()
        elif upgrade_satus == PlanUpgradeStatus.REMOVE_CANCELLATION:
            self.remove_cancel()
            self.set_remove_scheduled_cancel_popup_information()
            self.set_resume_success_popup()
        elif upgrade_satus == PlanUpgradeStatus.UPGRADE_PLAN_UNLIMITED:
            self.upgrade_unlimited()
            if self.upgrade_manager.upgrade_info is None:
                return
            self.set_upgrade_popup_information()
            self.set_upgrade_success_popup()
