import library as lib
import taxonomy as tax


COMMANDS = {
    "move": ("移动收藏", ("id", "to")),
    "rename": ("修改主题名称", ("id", "name")),
    "merge": ("合并主题", ("id", "to")),
    "split": ("拆分主题成员", ("id", "to", "members")),
    "hide": ("隐藏收藏", ("id",)),
    "pin": ("置顶收藏", ("id",)),
    "unhide": ("恢复收藏", ("id",)),
    "unpin": ("取消置顶", ("id",)),
}


def curate(args, state):
    rows, topics = state[:2]
    op, key = args.op, args.id
    values = {"id": key}
    if op in ("move", "merge", "split"):
        if args.to not in topics:
            raise lib.Error(f"找不到目标主题：{args.to}")
        values["to"] = args.to
    if op in ("rename", "merge", "split"):
        if key not in topics or key == tax.PENDING:
            raise lib.Error(f"找不到可编辑的主题：{key}")
        if op == "rename":
            if not tax.valid_name(args.name):
                raise lib.Error("主题名称格式有误")
            values["name"] = args.name
        else:
            if key == args.to or (op == "merge" and args.to.startswith(key + "/")):
                raise lib.Error("请选择另一个有效的目标主题")
            members = {row["id"] for row in rows.values() if row["topic"] == key or row["topic"].startswith(key + "/")}
            if op == "split":
                selected = [lib.lookup(item, rows)["id"] for item in args.members]
                outside = [item for item in selected if item not in members]
                if outside:
                    raise lib.Error("收藏不在源主题中：" + "、".join(outside))
                members = set(selected)
            values["items"] = sorted(members)
    else:
        values["id"] = lib.lookup(key, rows)["id"]
    lib.append_curation(op, **values)
    print(f"已记录 {COMMANDS[op][0]}：{values['id']}")


def release(args, state):
    key = args.id
    note = state[2].get(key)
    if key not in state[1] or not note:
        raise lib.Error(f"找不到主题笔记：{key}")
    lib.append_curation("release", id=key, hash=note.get("hash"))
    print(f"已交还给 AI：{key}")
