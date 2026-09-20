# -*- coding: utf-8 -*-
"""صفحه‌بندی یکپارچه — سازگان."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlencode

DEFAULT_PER_PAGE = 25
ALLOWED_PER_PAGE = (10, 25, 50, 100)
MAX_PER_PAGE = 100


def parse_page(args, default: int = 1) -> int:
    try:
        p = int(args.get('page', default) or default)
    except (TypeError, ValueError):
        p = default
    return max(1, p)


def parse_per_page(args, default: int = DEFAULT_PER_PAGE) -> int:
    try:
        n = int(args.get('per_page', default) or default)
    except (TypeError, ValueError):
        n = default
    if n not in ALLOWED_PER_PAGE:
        # clamp to nearest allowed or default
        if n < 10:
            n = 10
        elif n > MAX_PER_PAGE:
            n = MAX_PER_PAGE
        else:
            n = default
    return n


def paginate(
    items: Sequence[Any],
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict:
    """
    صفحه‌بندی لیست در حافظه.
    برمی‌گرداند: items, page, per_page, total, total_pages, has_prev, has_next, offset
    """
    total = len(items) if items is not None else 0
    per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), MAX_PER_PAGE))
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = max(1, min(int(page or 1), total_pages))
    offset = (page - 1) * per_page
    slice_items = list(items[offset: offset + per_page]) if items else []
    return {
        'items': slice_items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_rows': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'offset': offset,
        'from_item': (offset + 1) if total else 0,
        'to_item': min(offset + per_page, total) if total else 0,
    }


def paginate_query(
    conn,
    base_sql: str,
    params: Sequence[Any] = (),
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    count_sql: str = None,
    order_sql: str = 'ORDER BY id DESC',
) -> dict:
    """
    صفحه‌بندی در سطح SQL با COUNT جدا + LIMIT/OFFSET.
    base_sql باید بدون ORDER BY / LIMIT باشد (مثلاً SELECT ... FROM t WHERE ...).
    """
    per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), MAX_PER_PAGE))
    page = max(1, int(page or 1))

    if count_sql:
        row = conn.execute(count_sql, params).fetchone()
    else:
        # wrap
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM ({}) AS _pq'.format(base_sql),
            params,
        ).fetchone()
    try:
        total = int(row['c'] if row and 'c' in row.keys() else (row[0] if row else 0))
    except Exception:
        total = int(row[0]) if row else 0

    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    sql = f'{base_sql} {order_sql} LIMIT ? OFFSET ?'
    rows = conn.execute(sql, list(params) + [per_page, offset]).fetchall()

    return {
        'items': rows,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_rows': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'offset': offset,
        'from_item': (offset + 1) if total else 0,
        'to_item': min(offset + per_page, total) if total else 0,
    }


def page_window(page: int, total_pages: int, radius: int = 2) -> list:
    """
    لیست شماره صفحات برای نمایش با ellipsis.
    مثلاً: [1, None, 4, 5, 6, None, 20]  (None = …)
    """
    if total_pages <= 1:
        return [1] if total_pages == 1 else []
    pages = set()
    pages.add(1)
    pages.add(total_pages)
    for p in range(max(1, page - radius), min(total_pages, page + radius) + 1):
        pages.add(p)
    ordered = sorted(pages)
    result = []
    prev = None
    for p in ordered:
        if prev is not None and p - prev > 1:
            result.append(None)  # ellipsis
        result.append(p)
        prev = p
    return result


def build_page_qs(
    args: Mapping[str, Any],
    *,
    exclude: Iterable[str] = ('page',),
) -> str:
    """query string فعلی بدون page (و کلیدهای exclude) برای ساخت لینک صفحه‌بندی."""
    exclude_set = set(exclude) | {'page'}
    pairs = []
    try:
        # werkzeug ImmutableMultiDict
        if hasattr(args, 'items'):
            for key in args:
                if key in exclude_set:
                    continue
                vals = args.getlist(key) if hasattr(args, 'getlist') else [args.get(key)]
                for v in vals:
                    if v is None or v == '':
                        continue
                    pairs.append((key, v))
    except Exception:
        for k, v in dict(args or {}).items():
            if k in exclude_set or v is None or v == '':
                continue
            pairs.append((k, v))
    return urlencode(pairs)


def pagination_context(
    page_result: dict,
    args=None,
    *,
    per_page_choices: Sequence[int] = ALLOWED_PER_PAGE,
) -> dict:
    """دیکشنری آماده برای قالب _pagination.html و رندر لیست."""
    page = page_result['page']
    total_pages = page_result['total_pages']
    qs = build_page_qs(args or {})
    return {
        'page': page,
        'per_page': page_result['per_page'],
        'total_pages': total_pages,
        'total_rows': page_result['total_rows'],
        'total': page_result['total'],
        'has_prev': page_result['has_prev'],
        'has_next': page_result['has_next'],
        'from_item': page_result['from_item'],
        'to_item': page_result['to_item'],
        'page_window': page_window(page, total_pages),
        'page_qs': qs,
        'per_page_choices': list(per_page_choices),
    }
