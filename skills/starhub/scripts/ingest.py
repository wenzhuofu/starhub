import json
import random
import time
from urllib.error import HTTPError

import catalog
import library as lib
from sources import GitHub, OpenCLI, RateLimited, SOURCE_ERRORS, rate_limited, source_error
from views import rebuild


def fetched(source, cfg, known, rows, synced, full):
    if source == "github":
        yield from GitHub().saved(cfg["github"], lambda key: known(key.casefold()), full)
    elif source == "xhs":
        def known_action(key, action):
            return known(key) and action in lib.xhs_actions(rows[key])

        history = cfg.setdefault("xhs_history", {})
        if full:
            history.pop("tabs", None)
        yield from OpenCLI(source).xhs_saved(known_action, history, full)
    else:
        yield from OpenCLI(source).bili_saved(known, source not in synced, full, cfg.setdefault("bili_history", {}))


def merge_batch(rows, source, by_id, batch, full):
    date = lib.today()
    added, seen = 0, set()
    actions = {action: set() for action in lib.XHS_ACTIONS}
    for incoming in batch:
        raw = lib.raw_record(incoming)
        identity = raw["id"].casefold() if source == "github" else raw["id"]
        key = by_id.get(identity, raw["id"])
        if source == "xhs":
            for action in raw["via"]:
                actions[action].add(key)
        if identity in seen:
            continue
        seen.add(identity)
        prior = rows.get(key)
        if not prior:
            rows[key] = {**raw, "seen": date, "saved": raw["saved"] or date}
            added += 1
            continue
        if source == "xhs" and not full and "收藏" in prior["via"] and raw["via"] == ["点赞"]:
            raw.update({name: prior[name] for name in ("url", "title", "author", "folder")})
        prior.update({**raw, "id": key, "seen": prior["seen"] or date, "removed": "",
                      "via": prior["via"] if source == "xhs" else raw["via"],
                      "saved": raw["saved"] or prior["saved"] or date, "meta": {**prior["meta"], **raw["meta"]}})
    print(f"{lib.LABELS[source]:8} 新增 {added}")
    if source == "xhs":
        for identity in seen:
            key = by_id.get(identity, identity)
            previous = [] if full else rows[key]["via"]
            rows[key]["via"] = [action for action, keys in actions.items() if key in keys or action in previous]
        saved, liked = actions.values()
        print(f"小红书本次读取：收藏 {len(saved)}，点赞 {len(liked)}（两者都有 {len(saved & liked)}）")
    if full:
        for identity in sorted(by_id.keys() - seen):
            item = rows[by_id[identity]]
            if not item["removed"]:
                item["removed"] = date
                print(f"已下架 {item['id']}")
    return added


def print_pending(rows):
    print(f"待整理 {sum(row['source'] != 'github' and row['status'] == 'new' and lib.visible(row) for row in rows.values())} 条")


def backfill(rows, sources, limit):
    path = lib.state_path("body_failures.json")
    failures = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    candidates = sorted((row for row in rows.values() if row["source"] in sources
                         and row["source"] in ("xhs", "bili") and lib.visible(row)
                         and not row["has_body"] and failures.get(row["id"], 0) < 3),
                        key=lambda row: (row["saved"], row["seen"], row["id"]), reverse=True)
    added = 0
    for i, row in enumerate(candidates[:limit]):
        if i:
            time.sleep(random.uniform(3, 6))
        key = row["id"]
        try:
            body = OpenCLI(row["source"]).body(row).strip()
            if not body:
                raise lib.Error("没有可用正文")
        except SOURCE_ERRORS as exc:
            if (isinstance(exc, RateLimited) or isinstance(exc, HTTPError) and exc.code in (429, 461)
                    or rate_limited(str(exc))):
                print(f"正文已补 {added} 条。请求受限，本次同步已停止。")
                return added, True
            failures[key] = failures.get(key, 0) + 1
            lib.write(path, json.dumps(failures, ensure_ascii=False, indent=2) + "\n")
            print(f"正文读取失败 {key}（{failures[key]}/3）：{source_error(row['source'], exc)}")
        else:
            lib.write(lib.cache_path(row), body.replace("\r\n", "\n").replace("\r", "\n") + "\n")
            added += 1
            if key in failures:
                del failures[key]
                lib.write(path, json.dumps(failures, ensure_ascii=False, indent=2) + "\n")
    if candidates and limit:
        print(f"正文已补 {added} 条")
    return added, False


def sync(args):
    cfg = lib.config()
    selected = list(dict.fromkeys(args.source or cfg["sources"]))
    if any(source not in lib.LABELS for source in selected):
        raise lib.Error("来源可选 github、xhs、bili")
    synced = set(cfg.get("synced_sources", ()))
    rows = lib.raw_items()
    completed, updated, stopped = set(), False, False
    reports = []
    for source in selected:
        by_id = {(key.casefold() if source == "github" else key): key
                 for key, row in rows.items() if row["source"] == source}
        batch, complete = [], True
        try:
            batch.extend(fetched(source, cfg, by_id.__contains__, rows, synced, args.full))
        except SOURCE_ERRORS as exc:
            print(f"{lib.LABELS[source]:8} " + source_error(source, exc).removeprefix(lib.LABELS[source]))
            stopped = (isinstance(exc, RateLimited) or isinstance(exc, HTTPError) and exc.code in (429, 461)
                       or rate_limited(str(exc)))
            if source == "github" or not batch:
                reports.append(f"{lib.LABELS[source]} 失败")
                if stopped:
                    break
                continue
            complete = False
        if complete:
            completed.add(source)
            synced.add(source)
        count = merge_batch(rows, source, by_id, batch, args.full and complete)
        reports.append(f"{lib.LABELS[source]} 新增 {count}" + ("" if complete else "（保留断点）"))
        lib.put_raw(rows, [source])
        updated = True
        if stopped:
            break
    if updated:
        if completed:
            cfg.update(last_sync=lib.now(), synced_sources=sorted(synced))
        lib.put_config(cfg)
    if args.bodies and completed and not stopped:
        added, stopped = backfill(catalog.state()[0], completed, args.bodies)
        reports.append(f"正文新增 {added}" + ("（请求受限）" if stopped else ""))
    if updated:
        rebuild()
    lib.wiki_log("sync", "，".join(reports) or "0 个来源")
    print_pending(catalog.state()[0])
    return int(stopped or not completed)
