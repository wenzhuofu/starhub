import catalog
import library as lib
from sources import GitHub, OpenCLI, SOURCE_ERRORS, source_error
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
    print(f"待整理 {sum(row['status'] == 'new' and lib.visible(row) for row in rows.values())} 条")


def sync(args):
    cfg = lib.config()
    selected = list(dict.fromkeys(args.source or cfg["sources"]))
    if any(source not in lib.LABELS for source in selected):
        raise lib.Error("来源可选 github、xhs、bili")
    synced = set(cfg.get("synced_sources", ()))
    rows = lib.raw_items()
    succeeded, updated = False, False
    reports = []
    for source in selected:
        by_id = {(key.casefold() if source == "github" else key): key
                 for key, row in rows.items() if row["source"] == source}
        batch, complete = [], True
        try:
            batch.extend(fetched(source, cfg, by_id.__contains__, rows, synced, args.full))
        except SOURCE_ERRORS as exc:
            print(f"{lib.LABELS[source]:8} " + source_error(source, exc).removeprefix(lib.LABELS[source]))
            if source == "github" or not batch:
                reports.append(f"{lib.LABELS[source]} 失败")
                continue
            complete = False
        if complete:
            succeeded = True
            synced.add(source)
        count = merge_batch(rows, source, by_id, batch, args.full and complete)
        reports.append(f"{lib.LABELS[source]} 新增 {count}" + ("" if complete else "（保留断点）"))
        lib.put_raw(rows, [source])
        updated = True
    if updated:
        if succeeded:
            cfg.update(last_sync=lib.now(), synced_sources=sorted(synced))
        lib.put_config(cfg)
        rebuild()
    lib.wiki_log("sync", "，".join(reports) or "0 个来源")
    print_pending(catalog.state()[0])
    return int(not succeeded)
