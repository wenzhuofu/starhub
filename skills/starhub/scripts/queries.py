import index_db
import library as lib
import taxonomy as tax

VISIBLE = "item.status <> 'hidden' AND item.removed = ''"
ROW_LIMIT = 100
NEIGHBOR_LIMIT = 20
NOTE_LIMIT = 6000
SEARCH_FIELDS = ("clean_title", "scene", "excerpt", "topic", "entities")
SEARCH_WEIGHTS = (5, 3, 1, 2, 2)


def snippet(text, size):
    text = " ".join(text.split())
    return text if len(text) <= size else text[:size - 1] + "…"


def l0(row):
    return "  ".join((snippet(row["id"], 120), snippet(row["topic"], 50) or "—",
                      row["kind"] or "—", snippet(row["clean_title"], 40) or "—"))


def display(row, depth, entities=""):
    lines = [l0(row)]
    if depth >= 1:
        lines.append("  " + " · ".join(filter(None, [snippet(row["scene"], 20), snippet(entities, 75),
                                                       lib.LABELS[row["source"]], row["saved"]])))
    if depth == 2 and row["excerpt"]:
        lines.append("  " + snippet(row["excerpt"], 300))
    return "\n".join(lines)


def map_topics(args):
    with index_db.open_index() as conn:
        tree = conn.execute("""
            WITH RECURSIVE tree(id, name, size, summary, depth) AS (
                SELECT id, name, size, summary, 1 FROM topic WHERE parent = ''
                UNION ALL
                SELECT topic.id, topic.name, topic.size, topic.summary, tree.depth + 1
                FROM topic JOIN tree ON topic.parent = tree.id WHERE tree.depth < ?
            )
            SELECT * FROM tree ORDER BY (id = '待定' OR id LIKE '待定/%'), id
        """, (args.depth,))
        for row in tree:
            full = row["id"].rpartition("/")[0]
            label = f"{full}/{row['name']}" if full else row["name"]
            print(f"{'  ' * (row['depth'] - 1)}{snippet(label, 80)}  {row['size']}  {snippet(row['summary'], 80)}".rstrip())


SUBTREE = """
    subtree(id) AS (
        SELECT id FROM topic WHERE id = ?
        UNION ALL
        SELECT topic.id FROM topic JOIN subtree ON topic.parent = subtree.id
    )
"""


def topic(args, state):
    rows, topics, wiki, _, _ = state
    if args.id not in topics:
        raise lib.Error(f"找不到主题：{args.id}")
    note = wiki.get(args.id)
    if note:
        body = note["body"].rstrip()
        print(body[:NOTE_LIMIT] + ("\n…（笔记较长，完整内容见 wiki/" + note["file"] + "）"
                                  if len(body) > NOTE_LIMIT else ""))
    else:
        print(f"# {topics[args.id]['name']}\n还没有主题笔记。")
    if args.items:
        with index_db.open_index() as conn:
            group = {row[0] for row in conn.execute(f"WITH RECURSIVE {SUBTREE} SELECT id FROM subtree", (args.id,))}
        members = [row for row in rows.values() if row["topic"] in group and row["source"] != "github" and lib.visible(row)]
        members.sort(key=lambda row: (row["pinned"], row["saved"], row["seen"], row["id"]), reverse=True)
        if members:
            print("\n## 成员")
            for row in members[:args.items]:
                print(l0(row))


def search_term(variants, number):
    long = [word for word in variants if len(word) >= 3]
    short = [word for word in variants if len(word) < 3]
    ctes, params, queries = [], [], []
    if long:
        match = " OR ".join('"' + word.replace('"', '""') + '"' for word in long)
        ctes.append(f"rank_{number} AS MATERIALIZED ("
                    "SELECT id, bm25(search, 0, 5, 3, 1, 2, 2) AS rank FROM search WHERE search MATCH ?)")
        queries.append(f"SELECT id, rank FROM rank_{number}")
        params.append(match)
    if short:
        # Trigram cannot match a one- or two-character term. Use the same field
        # weights and BM25 saturation for the substring fallback.
        per_field = []
        for field, weight in zip(SEARCH_FIELDS, SEARCH_WEIGHTS):
            hit = " OR ".join(f"instr(lower({field}), ?) > 0" for _ in short)
            per_field.append(f"{weight} * ({hit})")
            params.extend(short)
        ctes.append(f"short_{number} AS MATERIALIZED (SELECT id, "
                    "-0.0000022 * weight / (weight + 1.2) AS rank "
                    f"FROM (SELECT id, {' + '.join(per_field)} AS weight FROM search))")
        queries.append(f"SELECT id, rank FROM short_{number} WHERE rank < 0")
    ctes.append(f"term_{number} AS (SELECT id, min(rank) AS rank FROM ({' UNION ALL '.join(queries)}) GROUP BY id)")
    return ctes, params


def find(args):
    terms = list(dict.fromkeys(word.strip().casefold() for word in args.words if word.strip()))
    if not terms or any("\0" in word for word in terms) or len(terms) > 16:
        raise lib.Error("请提供 1–16 个关键词")
    if args.since and lib.date(args.since) != args.since:
        raise lib.Error("--since 须为 YYYY-MM-DD")
    ctes, params, joins, ranks = [], [], [], []
    synonyms = tax.load()["synonyms"]
    for number, term in enumerate(terms):
        group, values = search_term(tax.alternatives(term, synonyms), number)
        ctes.extend(group)
        params.extend(values)
        name = f"term_{number}"
        joins.append(f"JOIN {name} USING(id)")
        ranks.append(f"{name}.rank")
    filters = [] if args.all else [VISIBLE]
    if args.topic:
        ctes.append(SUBTREE)
        params.append(args.topic)
        filters.append("item.topic IN (SELECT id FROM subtree)")
    for column, value, comparison in (("kind", args.kind, "="), ("source", args.source, "="), ("saved", args.since, ">=")):
        if value:
            filters.append(f"item.{column} {comparison} ?")
            params.append(value)
    where = " AND ".join(filters) or "1"
    query = (f"WITH RECURSIVE {', '.join(ctes)} SELECT item.*, search.entities FROM item "
             f"JOIN search USING(id) {' '.join(joins)} WHERE {where} "
             f"ORDER BY {' + '.join(ranks)}, item.saved DESC, item.id LIMIT ?")
    with index_db.open_index() as conn:
        hits = conn.execute(query, (*params, args.limit)).fetchall()
    for row in hits:
        print(display(row, args.depth, row["entities"]))
    if not hits:
        print("没有找到。换个说法，或用更短的词。")


def explain(args):
    key = args.id
    with index_db.open_index() as conn:
        item = conn.execute("SELECT * FROM item JOIN search USING(id) WHERE id = ?", (key,)).fetchone()
        row = conn.execute("SELECT * FROM topic WHERE id = ?", (key,)).fetchone()
        entity = conn.execute("SELECT * FROM entity WHERE id = ?", (key,)).fetchone()
        ghost = conn.execute("SELECT 1 FROM edge WHERE dst = ? AND rel = 'recommends_tool'", (key,)).fetchone()
        if item:
            print(display(item, 1, item["entities"]))
        elif row:
            print(f"{snippet(key, 100)}  {snippet(row['name'], 80)}  {row['size']}  {snippet(row['summary'], 80)}".rstrip())
        elif entity:
            print(snippet(entity["id"], 120))
        elif ghost:
            print(f"{snippet(key, 120)}  待分拣")
        else:
            raise lib.Error(f"找不到条目、主题或实体：{key}")
        neighbors = conn.execute("""
            SELECT CASE WHEN src = ? THEN dst ELSE src END AS neighbor, rel, by
            FROM edge WHERE src = ? OR dst = ? ORDER BY rel, neighbor LIMIT ?
        """, (key, key, key, NEIGHBOR_LIMIT + 1)).fetchall()
    for link in neighbors[:NEIGHBOR_LIMIT]:
        print(f"  {link['rel']}  {snippet(link['neighbor'], 120)}  [{link['by']}]")
    if len(neighbors) > NEIGHBOR_LIMIT:
        print(f"  …（仅显示前 {NEIGHBOR_LIMIT} 条关系）")
