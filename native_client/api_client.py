# -*- coding: utf-8 -*-
"""Thin HTTP client used by the native (PyQt5) Sazgan app.

Reuses the server's existing session-cookie login (POST to /login, same
as the browser form) so no backend changes are needed for authentication.
For screens that already have a JSON API (e.g. /api/lookup_warranty/<serial>)
this calls them directly. Screens that only render HTML today will need a
small JSON endpoint added to the matching routes/*.py file as each native
screen is built - see README.md in this folder.
"""
from __future__ import annotations
import time
import html
import re

import requests
from PyQt5.QtCore import pyqtSignal, QObject


class ApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SessionExpiredError(ApiError):
    """Raised when the server reports that the authenticated session expired."""
    pass


class SazganClient(QObject):
    sessionExpired = pyqtSignal()

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SazganNativeClient/1.0"})
        self.logged_in = False
        self.username = None
        self.csrf_token = None

    # ---- connectivity ----------------------------------------------------
    def ping(self, timeout=6):
        try:
            r = self.session.get(self.base_url + "/login", timeout=timeout)
            return r.status_code < 500, ""
        except requests.exceptions.RequestException as e:
            return False, str(e)

    # ---- auth ---------------------------------------------------------
    def login(self, username: str, password: str, timeout=8):
        """Logs in using the same session-cookie flow as the browser form.
        Returns (ok: bool, error_message: str).
        """
        try:
            # Warm up: some setups issue a CSRF cookie on GET first.
            self.session.get(self.base_url + "/login", timeout=timeout)
            resp = self.session.post(
                self.base_url + "/login",
                data={"username": username, "password": password},
                timeout=timeout,
                allow_redirects=True,
            )
        except requests.exceptions.ConnectionError:
            return False, "ارتباط با سرور برقرار نشد. آدرس سرور و روشن بودن سرویس سازگان را بررسی کنید."
        except requests.exceptions.Timeout:
            return False, "پاسخ سرور بیش از حد طول کشید. لطفاً دوباره تلاش کنید."
        except requests.exceptions.RequestException:
            return False, "ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید."

        # On success the server redirects to '/', so the final URL won't
        # contain '/login' and the page won't be the login form again.
        if resp.status_code < 400 and "/login" not in resp.url:
            self.logged_in = True
            self.username = username
            self._refresh_csrf_token()
            return True, ""
        if resp.status_code >= 500:
            return False, "ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید."
        return False, "نام کاربری یا رمز عبور نادرست است."

    def logout(self):
        try:
            self.session.get(self.base_url + "/logout", timeout=6)
        except requests.exceptions.RequestException:
            pass
        self.logged_in = False
        self.username = None
        self.csrf_token = None

    def _refresh_csrf_token(self, timeout=8):
        """Fetches a fresh csrf_token for this session (call after login and
        again if a POST ever comes back 400 due to an expired/rotated token).
        """
        try:
            data = self.get_json("/api/native/csrf-token", timeout=timeout)
            self.csrf_token = data.get("csrf_token")
        except ApiError:
            self.csrf_token = None
        return self.csrf_token

    @staticmethod
    def _rewind_uploads(files):
        """Rewind upload streams before a network retry when possible."""
        if not files:
            return
        values = files.values() if hasattr(files, "values") else []
        for value in values:
            stream = None
            if isinstance(value, (tuple, list)) and len(value) >= 2:
                stream = value[1]
            elif hasattr(value, "read"):
                stream = value
            if stream is not None and hasattr(stream, "seek"):
                try:
                    stream.seek(0)
                except (OSError, ValueError):
                    pass

    def _request_with_network_retry(self, method: str, url: str, timeout, **kwargs):
        """Perform one request, retrying only connection/timeout failures.

        Attempts: initial + 2 retries, with 0.5s then 1.0s backoff. HTTP
        responses (including 400/401/403/500) are never retried here.
        """
        delay = 0.5
        for attempt in range(3):
            try:
                return self.session.request(method, url, timeout=timeout, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                if attempt >= 2:
                    raise
                self._rewind_uploads(kwargs.get("files"))
                time.sleep(delay)
                delay *= 2

    def _post_form_once(self, path: str, data: dict | None, files, timeout):
        """Single POST attempt (with network-failure retry), no CSRF handling."""
        headers = {"X-CSRF-Token": self.csrf_token} if self.csrf_token else {}
        try:
            r = self._request_with_network_retry(
                "POST",
                self.base_url + path,
                timeout,
                data=data or {},
                files=files,
                headers=headers,
            )
        except requests.exceptions.ConnectionError as e:
            raise ApiError("ارتباط با سرور برقرار نشد. اتصال شبکه و آدرس سرور را بررسی کنید.") from e
        except requests.exceptions.Timeout as e:
            raise ApiError("پاسخ سرور بیش از حد طول کشید. لطفاً دوباره تلاش کنید.") from e
        except requests.exceptions.RequestException as e:
            raise ApiError("ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید.") from e
        if r.status_code == 401:
            self.logged_in = False
            self.sessionExpired.emit()
            raise SessionExpiredError("نشست شما منقضی شده، دوباره وارد شوید", 401)
        return r

    def _post_form(self, path: str, data: dict | None = None, files=None, timeout=15):
        """POST helper that attaches the CSRF token, retries network failures,
        and separately retries exactly once on HTTP 400 after refreshing an
        expired/rotated CSRF token.

        This CSRF-retry is a distinct, self-healing mechanism from network
        retry above: a 400 on a POST is most often the server rejecting a
        stale token, and a single silent refresh+retry fixes it without
        surfacing a generic error to the user. It is capped at one retry so
        a server that keeps rejecting the token (e.g. genuinely bad request
        data) fails fast instead of looping.
        """
        if self.csrf_token is None:
            self._refresh_csrf_token()
        r = self._post_form_once(path, data, files, timeout)
        if r.status_code == 400:
            self._rewind_uploads(files)
            old_token = self.csrf_token
            self._refresh_csrf_token(timeout=timeout)
            if self.csrf_token and self.csrf_token != old_token:
                r = self._post_form_once(path, data, files, timeout)
        return r

    # ---- JSON API helpers -------------------------------------------------
    def get_json(self, path: str, timeout=8):
        try:
            r = self._request_with_network_retry(
                "GET", self.base_url + path, timeout
            )
        except requests.exceptions.ConnectionError as e:
            raise ApiError("ارتباط با سرور برقرار نشد. اتصال شبکه و آدرس سرور را بررسی کنید.") from e
        except requests.exceptions.Timeout as e:
            raise ApiError("پاسخ سرور بیش از حد طول کشید. لطفاً دوباره تلاش کنید.") from e
        except requests.exceptions.RequestException as e:
            raise ApiError("ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید.") from e
        if r.status_code == 401:
            self.logged_in = False
            self.sessionExpired.emit()
            raise SessionExpiredError("نشست شما منقضی شده، دوباره وارد شوید", 401)
        if r.status_code >= 400:
            raise ApiError(f"سرور خطا داد (کد {r.status_code})", r.status_code)
        try:
            return r.json()
        except ValueError:
            raise ApiError("پاسخ سرور JSON نبود - احتمالاً این صفحه هنوز API ندارد.")

    def lookup_warranty(self, serial: str):
        return self.get_json(f"/api/lookup_warranty/{serial}")

    def unread_notifications_count(self):
        data = self.get_json("/api/native/notifications")
        return {"count": int(data.get("unread_count") or 0)}

    # ---- warehouse ---------------------------------------------
    def warehouse_internal(self, q: str = ""):
        return self.get_json(f"/api/native/warehouse/internal?q={q}")

    def warehouse_external(self, q: str = "", province: str = ""):
        return self.get_json(f"/api/native/warehouse/external?q={q}&province={province}")

    # ---- data hub (import/export) -------------------------------
    def data_hub_targets(self):
        return self.get_json("/api/native/data-hub/targets")

    def export_file(self, module: str, timeout=60):
        """Downloads the exported Excel file for a module. Returns (filename, content_bytes)."""
        try:
            r = self.session.get(
                self.base_url + f"/settings/data-hub/export?module={module}&format=excel",
                timeout=timeout,
            )
        except requests.exceptions.ConnectionError as e:
            raise ApiError("ارتباط با سرور برقرار نشد. اتصال شبکه و آدرس سرور را بررسی کنید.") from e
        except requests.exceptions.Timeout as e:
            raise ApiError("پاسخ سرور بیش از حد طول کشید. لطفاً دوباره تلاش کنید.") from e
        except requests.exceptions.RequestException as e:
            raise ApiError("ارتباط با سرور با خطا مواجه شد. لطفاً دوباره تلاش کنید.") from e
        if r.status_code >= 400 or "result=error" in r.url:
            raise ApiError("خروجی گرفتن ناموفق بود (دسترسی یا ماژول نامعتبر).")
        filename = f"{module}.xlsx"
        cd = r.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip().strip('"')
        return filename, r.content

    def import_file(self, module: str, local_path: str, timeout=120):
        """Uploads a local .xlsx file for a module. Returns dict: ok, count, msg."""
        with open(local_path, "rb") as f:
            files = {"excel_file": (local_path.split("/")[-1].split("\\")[-1], f,
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            data = {"module": module}
            r = self._post_form("/settings/data-hub/import", data=data, files=files, timeout=timeout)
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(r.url).query)
        result = (qs.get("result", [""])[0])
        return {
            "ok": result == "ok",
            "count": qs.get("count", [""])[0],
            "msg": qs.get("msg", [""])[0],
        }

    # ---- finance --------------------------------------------------
    def finance_reps_dashboard(self, year=None, month=None):
        q = f"?year={year}&month={month}" if year and month else ""
        return self.get_json(f"/api/native/finance/reps-dashboard{q}")

    def finance_wage_history(self):
        return self.get_json("/api/native/finance/wage-history")

    def my_wages(self, year=None, month=None):
        q = f"?year={year}&month={month}" if year and month else ""
        return self.get_json(f"/api/native/finance/my-wages{q}")

    # ---- reports ---------------------------------------------------
    def reports_dashboard(self):
        return self.get_json("/api/native/reports/dashboard")

    def reports_management(self):
        return self.get_json("/api/native/reports/management")

    # ---- improvements ---------------------------------------------
    def wage_report(self, year=None, month=None):
        q = f"?year={year}&month={month}" if year and month else ""
        return self.get_json(f"/api/native/finance/wage-report{q}")

    def manager_dashboard(self):
        return self.get_json("/api/native/reports/manager-dashboard")

    def audit_filter(self, q: str = "", action: str = ""):
        return self.get_json(f"/api/native/security/audit-filter?q={q}&action={action}")

    # ---- support (internal staff chat) ----------------------------
    def support_inbox(self, status: str = "باز", q: str = ""):
        return self.get_json(f"/api/native/support/inbox?status={status}&q={q}")

    def support_thread_messages(self, thread_id: int, after: int = 0):
        return self.get_json(f"/api/support/thread/{thread_id}/messages?after={after}")

    def support_thread_send(self, thread_id: int, body: str, reply_to_id=None, timeout=15, file_path=None):
        data = {"body": body}
        if reply_to_id:
            data["reply_to_id"] = reply_to_id
        files = None
        handle = None
        try:
            if file_path:
                import os
                handle = open(file_path, "rb")
                files = {"attachment": (os.path.basename(file_path), handle, "application/octet-stream")}
                r = self._post_form(f"/api/support/thread/{thread_id}/send", data=data, files=files, timeout=timeout)
            else:
                r = self._post_form(f"/api/support/thread/{thread_id}/send", data=data, timeout=timeout)
            if r.status_code >= 400:
                raise ApiError(f"ارسال پیام ناموفق بود (کد {r.status_code})")
            return r.json()
        finally:
            if handle:
                handle.close()

    def support_thread_close(self, thread_id: int, action: str = "close"):
        r = self._post_form(f"/api/native/support/thread/{thread_id}/close", data={"action": action}, timeout=10)
        if r.status_code >= 400:
            raise ApiError("عملیات ناموفق بود.")
        return r.json()

    # ---- service.py (customer-affairs: hub + archive/list layer) --
    def service_hub(self):
        return self.get_json("/api/native/service/hub")

    def service_archive(self, slug: str, filters: dict | None = None):
        q = self._qs(filters)
        return self.get_json(f"/api/native/service/{slug}/archive{q}")

    def installation_requests(self, filters: dict | None = None):
        q = self._qs(filters)
        return self.get_json(f"/api/native/service/installation/requests{q}")

    def installation_registers(self, filters: dict | None = None):
        q = self._qs(filters)
        return self.get_json(f"/api/native/service/installation/registers{q}")

    def inspection_list(self, tab: str = "requests", filters: dict | None = None):
        f = dict(filters or {})
        f["tab"] = tab
        q = self._qs(f)
        return self.get_json(f"/api/native/service/inspection/list{q}")

    # ---- service - new-record creation ("ثبت جدید" tab) ----------
    def _create(self, path: str, data: dict, files=None, timeout=20):
        r = self._post_form(path, data=data, files=files, timeout=timeout)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"ثبت ناموفق بود (کد {r.status_code}).")
        return payload  # {"ok": True, "id": <new_id>}

    def service_form_options(self):
        return self.get_json("/api/native/service/form-options")

    def create_internal_repair(self, data: dict):
        return self._create("/api/native/service/internal-repair/new", data)

    def create_external_repair(self, data: dict):
        return self._create("/api/native/service/external-repair/new", data)

    def create_installation_request(self, data: dict):
        return self._create("/api/native/service/installation/request-new", data)

    def create_installation_register(self, data: dict, report_file_path: str):
        with open(report_file_path, "rb") as f:
            fname = report_file_path.split("/")[-1].split("\\")[-1]
            files = {"report_file": (fname, f, "application/octet-stream")}
            return self._create("/api/native/service/installation/register-new", data, files=files)

    def create_inspection_request(self, data: dict):
        return self._create("/api/native/service/inspection/request-new", data)

    def create_inspection_report(self, data: dict, report_file_path: str | None = None):
        files = None
        if report_file_path:
            f = open(report_file_path, "rb")
            fname = report_file_path.split("/")[-1].split("\\")[-1]
            files = {"report_file": (fname, f, "application/octet-stream")}
        try:
            return self._create("/api/native/service/inspection/report-new", data, files=files)
        finally:
            if files:
                files["report_file"][1].close()

    # ---- internal-repair detail view + actions --------------------
    def internal_repair_detail(self, req_id: int):
        return self.get_json(f"/api/native/service/internal-repair/detail/{req_id}")

    def internal_repair_action(self, req_id: int, data: dict):
        r = self._post_form(f"/api/native/service/internal-repair/action/{req_id}", data=data, timeout=20)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"عملیات ناموفق بود (کد {r.status_code}).")
        return payload

    # ---- external-repair / installation / inspection detail ------
    def external_repair_detail(self, req_id: int):
        return self.get_json(f"/api/native/service/external-repair/detail/{req_id}")

    def external_repair_action(self, req_id: int, data: dict):
        return self._act(f"/api/native/service/external-repair/action/{req_id}", data)

    def installation_request_detail(self, req_id: int):
        return self.get_json(f"/api/native/service/installation/request-detail/{req_id}")

    def installation_request_action(self, req_id: int, data: dict):
        return self._act(f"/api/native/service/installation/request-action/{req_id}", data)

    def installation_register_detail(self, req_id: int):
        return self.get_json(f"/api/native/service/installation/register-detail/{req_id}")

    def installation_register_action(self, req_id: int, data: dict):
        return self._act(f"/api/native/service/installation/register-action/{req_id}", data)

    def inspection_detail(self, req_id: int):
        return self.get_json(f"/api/native/service/inspection/detail/{req_id}")

    def inspection_action(self, req_id: int, data: dict):
        return self._act(f"/api/native/service/inspection/action/{req_id}", data)

    def _act(self, path: str, data: dict):
        r = self._post_form(path, data=data, timeout=20)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"عملیات ناموفق بود (کد {r.status_code}).")
        return payload

    def upload_attachment(self, req_id: int, file_path: str, label: str = "پیوست"):
        with open(file_path, "rb") as f:
            fname = file_path.split("/")[-1].split("\\")[-1]
            files = {"attachment": (fname, f, "application/octet-stream")}
            data = {"label": label, "redirect_to": "/"}
            r = self._post_form(f"/attachments/upload/{req_id}", data=data, files=files, timeout=30)
        if r.status_code >= 400:
            raise ApiError(f"آپلود پیوست ناموفق بود (کد {r.status_code}).")
        return True

    def delete_attachment(self, att_id: int):
        """Deletes an attachment using the same web endpoint/permission
        logic as the browser (only the uploader or reception can delete)."""
        r = self._post_form(f"/attachments/delete/{att_id}", data={"redirect_to": "/"}, timeout=15)
        if r.status_code >= 400:
            raise ApiError(f"حذف پیوست ناموفق بود (کد {r.status_code}).")
        return True

    @staticmethod
    def _qs(filters: dict | None) -> str:
        if not filters:
            return ""
        from urllib.parse import urlencode
        clean = {k: v for k, v in filters.items() if v not in (None, "", False)}
        if not clean:
            return ""
        return "?" + urlencode(clean)

    # ---- main.py (home dashboard / role cartable) -----------------
    def home_dashboard(self):
        return self.get_json("/api/native/home")

    def native_me(self):
        return self.get_json("/api/native/me")

    def login_info(self, timeout=6):
        """Public company/support info shown on the login screen, before
        authentication. Never raises - a missing/unreachable server should
        degrade to an empty support panel, not block the login form."""
        try:
            return self.get_json("/api/native/login-info", timeout=timeout)
        except ApiError:
            return {}

    def global_search(self, q: str = ""):
        from urllib.parse import quote_plus
        return self.get_json(f"/api/native/search?q={quote_plus(q)}")

    def native_notifications(self):
        return self.get_json("/api/native/notifications")

    def mark_notification_read(self, notification_id: int):
        r = self._post_form(f"/api/native/notifications/read/{int(notification_id)}", timeout=10)
        if r.status_code >= 400:
            raise ApiError(f"خواندن اعلان ناموفق بود (کد {r.status_code})")
        return r.json()

    def mark_all_notifications_read(self):
        r = self._post_form("/api/native/notifications/read-all", timeout=10)
        if r.status_code >= 400:
            raise ApiError(f"خواندن اعلان‌ها ناموفق بود (کد {r.status_code})")
        return r.json()

    # ---- settings.py (user management - first slice) --------------
    def settings_representatives(self, q=''):
        return self.get_json(f"/api/native/settings/representatives{self._qs({'q':q})}")
    def representative_new(self, data): return self._create('/api/native/settings/representatives/new', data)
    def representative_edit(self, rep_id, data): return self._create(f'/api/native/settings/representatives/{rep_id}/edit', data)
    def representative_archive(self, rep_id): return self._post_form(f'/api/native/settings/representatives/{rep_id}/archive')
    def settings_access(self): return self.get_json('/api/native/settings/access')
    def settings_access_save(self, data): return self._create('/api/native/settings/access/save', data)
    def account_profile(self): return self.get_json('/api/native/account/profile')
    def account_profile_save(self, data): return self._create('/api/native/account/profile/save', data)
    def account_password_change(self, data): return self._create('/api/native/account/password', data)
    def settings_users(self):
        return self.get_json("/api/native/settings/users")

    def settings_users_archive(self):
        return self.get_json("/api/native/settings/users/archive")

    def settings_user_new(self, data: dict):
        return self._create("/api/native/settings/users/new", data)

    def settings_user_deactivate(self, user_id: int):
        r = self._post_form(f"/api/native/settings/users/{user_id}/deactivate", timeout=10)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"غیرفعال‌سازی ناموفق بود (کد {r.status_code}).")
        return payload

    def settings_user_activate(self, user_id: int):
        r = self._post_form(f"/api/native/settings/users/{user_id}/activate", timeout=10)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"فعال‌سازی ناموفق بود (کد {r.status_code}).")
        return payload

    # ---- customer affairs - contacts / announcements -------------
    def customer_affairs_contacts(self, q: str | None = None):
        return self.get_json(f"/api/native/customer-affairs/contacts{self._qs({'q': q})}")

    def customer_affairs_contact_new(self, data: dict):
        return self._create("/api/native/customer-affairs/contacts/new", data)

    def customer_affairs_announcements(self, q: str | None = None, status: str | None = None):
        return self.get_json(
            f"/api/native/customer-affairs/announcements{self._qs({'q': q, 'status': status})}"
        )

    def customer_affairs_announcement_handled(self, ann_id: int):
        r = self._post_form(f"/api/native/customer-affairs/announcements/{ann_id}/handled", timeout=10)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"عملیات ناموفق بود (کد {r.status_code}).")
        return payload

    # ---- settings.py (customers management - second slice) ------
    def settings_customers(self, q: str | None = None):
        return self.get_json(f"/api/native/settings/customers{self._qs({'q': q})}")

    def settings_customer_new(self, data: dict):
        return self._create("/api/native/settings/customers/new", data)

    def settings_customer_edit(self, customer_id: int, data: dict):
        return self._create(f"/api/native/settings/customers/{customer_id}/edit", data)

    def settings_customer_archive(self, customer_id: int):
        r = self._post_form(f"/api/native/settings/customers/{customer_id}/archive", timeout=10)
        try:
            payload = r.json()
        except ValueError:
            raise ApiError(f"پاسخ سرور نامعتبر بود (کد {r.status_code}).")
        if r.status_code >= 400 or not payload.get("ok"):
            raise ApiError(payload.get("error") or f"آرشیو ناموفق بود (کد {r.status_code}).")
        return payload

    # ---- remaining native cards --------------------------------
    def wage_rates(self, q=''): return self.get_json(f"/api/native/finance/wage-rates{self._qs({'q':q})}")
    def wage_rate_create(self, data): return self._create('/api/native/finance/wage-rates/new', data)
    def finance_files(self, q=''): return self.get_json(f"/api/native/finance/files{self._qs({'q':q})}")
    def finance_settlements(self, q=''):
        return self.get_json(f"/api/native/finance/settlements{self._qs({'q':q})}")
    def finance_settlement_detail(self, rep_id, year=None, month=None):
        return self.get_json(f"/api/native/finance/settlement/{rep_id}{self._qs({'year':year,'month':month})}")
    def finance_settle(self, rep_id, data):
        return self._create(f"/api/native/finance/settlement/{rep_id}", data)
    def finance_settlement_receipt(self, settlement_id):
        return self.get_json(f"/api/native/finance/settlement/receipt/{settlement_id}")
    def finance_invoices(self, q=''):
        return self.get_json(f"/api/native/finance/invoices{self._qs({'q':q})}")
    def finance_invoice_save(self, request_id, invoice_number, invoice_date):
        return self._create(f"/api/native/finance/invoices/{request_id}", {'invoice_number':invoice_number, 'invoice_date':invoice_date})
    def delay_matrix(self, kind='internal', serial='', province='', only_delayed=False): return self.get_json(f"/api/native/reports/delay-matrix{self._qs({'kind':kind,'serial':serial,'province':province,'only_delayed':'1' if only_delayed else ''})}")
    def report_stage_delays(self, q=''): return self.get_json(f"/api/native/reports/stage-delays{self._qs({'q':q})}")
    # ---- UI-only settings backed by existing HTML route (no backend route change) ----
    def chat_emojis_get(self):
        try:
            r = self.session.get(self.base_url + "/settings/chat-emojis", timeout=8)
            if r.status_code == 401:
                raise SessionExpiredError("نشست منقضی شده است.", r.status_code)
            r.raise_for_status()
            m = re.search(r'<textarea[^>]*name=["\\\']emojis["\\\'][^>]*>(.*?)</textarea>', r.text, re.S | re.I)
            raw = html.unescape(m.group(1)) if m else ""
            return [x.strip() for x in raw.split(",") if x.strip()]
        except requests.exceptions.RequestException as e:
            raise ApiError(str(e))

    def chat_emojis_save(self, emojis):
        try:
            r = self._post_form("/settings/chat-emojis", {"emojis": ", ".join(emojis)}, timeout=8)
            if r.status_code >= 400:
                raise ApiError(f"خطای سرور: {r.status_code}", r.status_code)
            return True
        except requests.exceptions.RequestException as e:
            raise ApiError(str(e))

    def products_devices(self,q=''): return self.get_json(f"/api/native/settings/products/devices{self._qs({'q':q})}")
    def product_device_add(self,device_type,model): return self._create('/api/native/settings/products/devices/new',{'device_type':device_type,'model':model})
    def product_device_edit(self, item_id, data): return self._create(f'/api/native/settings/products/devices/{item_id}/edit', data)
    def product_device_delete(self, item_id): return self._post_form(f'/api/native/settings/products/devices/{item_id}/delete')
    def products_parts(self,q=''): return self.get_json(f"/api/native/settings/products/parts{self._qs({'q':q})}")
    def product_part_add(self,part_name): return self._create('/api/native/settings/products/parts/new',{'part_name':part_name})
    def product_part_edit(self, item_id, data): return self._create(f'/api/native/settings/products/parts/{item_id}/edit', data)
    def product_part_delete(self, item_id): return self._post_form(f'/api/native/settings/products/parts/{item_id}/delete')
    def products_warranty(self,q=''): return self.get_json(f"/api/native/settings/products/warranty{self._qs({'q':q})}")
    def product_warranty_add(self,serial,customer_name): return self._create('/api/native/settings/products/warranty/new',{'serial_number':serial,'customer_name':customer_name})
    def product_warranty_edit(self, item_id, data): return self._create(f'/api/native/settings/products/warranty/{item_id}/edit', data)
    def product_warranty_delete(self, item_id): return self._post_form(f'/api/native/settings/products/warranty/{item_id}/delete')
    def calendar_holidays(self): return self.get_json('/api/native/settings/calendar')
    def calendar_add(self,date,title): return self._create('/api/native/settings/calendar/new',{'holiday_date':date,'title':title})
    def calendar_edit(self, item_id, date, title): return self._create(f'/api/native/settings/calendar/{item_id}/edit',{'holiday_date':date,'title':title})
    def calendar_delete(self, item_id): return self._post_form(f'/api/native/settings/calendar/{item_id}/delete')
    def company_get(self): return self.get_json('/api/native/settings/company')
    def company_save(self,data): return self._create('/api/native/settings/company/save',data)
    def app_lists(self,key,q=''): return self.get_json(f"/api/native/settings/app-lists{self._qs({'key':key,'q':q})}")
    def app_list_add(self,key,value): return self._create('/api/native/settings/app-lists/new',{'list_key':key,'value':value})
    def app_list_edit(self, item_id, value): return self._create(f'/api/native/settings/app-lists/{item_id}/edit',{'value':value})
    def app_list_delete(self, item_id): return self._post_form(f'/api/native/settings/app-lists/{item_id}/delete')
    def geo(self): return self.get_json('/api/native/settings/geo')
    def geo_cities(self,province): return self.get_json(f"/api/native/settings/geo/cities{self._qs({'province':province})}")
    def distance(self): return self.get_json('/api/native/settings/distance')
    def distance_seed(self): return self._create('/api/native/settings/distance/seed',{})
    def distance_set_factor(self,road_factor): return self._create('/api/native/settings/distance/factor',{'road_factor':road_factor})
    def distance_set_method(self,distance_method,osrm_url=''): return self._create('/api/native/settings/distance/method',{'distance_method':distance_method,'osrm_url':osrm_url})
    def system_info(self): return self.get_json('/api/native/settings/system')
    def about_info(self): return self.get_json('/api/native/settings/about')
    def changelog(self): return self.get_json('/api/native/settings/changelog')
    def activation(self): return self.get_json('/api/native/settings/activation')
    def activation_activate(self,license_key,license_owner=''): return self._create('/api/native/settings/activation/activate',{'license_key':license_key,'license_owner':license_owner})
    def help_tips(self): return self.get_json('/api/native/settings/help-tips')
    def help_tips_save(self,data): return self._create('/api/native/settings/help-tips/save',data)
    def device_folders(self,q=''): return self.get_json(f"/api/native/settings/device-folders{self._qs({'q':q})}")
