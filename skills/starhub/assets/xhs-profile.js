async (tab, userId, offset, pages, resumeCursor, resumePage) => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const getStore = () => document.querySelector('#app')?.__vue_app__
    ?.config?.globalProperties?.$pinia?._s?.get('user');

  let user;
  let index;
  const onSelectedList = () => user?.activeTab?.query === tab &&
    (tab === 'liked' || user.activeSubTab?.query === 'note');
  for (let attempt = 0; attempt < 20; attempt++) {
    user = getStore();
    index = tab === 'liked' ? user?.activeTab?.index : user?.activeSubTab?.index;
    if (onSelectedList() && typeof user.noteQueries?.[index]?.hasMore === 'boolean' &&
        (user.notes?.[index]?.length || user.userNoteFetchingStatus?.[index] === 'resolved' ||
         !user.noteQueries[index].hasMore)) break;
    await wait(250);
  }
  if (user?.loggedIn === false || location.pathname.startsWith('/login')) return { error: 'login' };
  if (location.hostname !== 'www.xiaohongshu.com' || location.pathname !== '/user/profile/' + userId ||
      !onSelectedList() ||
      !Array.isArray(user.notes?.[index]) || typeof user.noteQueries?.[index]?.hasMore !== 'boolean' ||
      typeof user.fetchNotes !== 'function') return { error: 'profile' };

  const query = user.noteQueries[index];
  if (resumeCursor && query.hasMore) {
    query.cursor = new TextDecoder().decode(Uint8Array.from(atob(resumeCursor), (c) => c.charCodeAt(0)));
    query.page = resumePage;
    offset = user.notes[index].length;
  }

  let stalled = false;
  let error = '';
  let cursor = query.cursor;
  let page = query.page;
  for (let i = 0; i < pages && user.noteQueries[index].hasMore; i++) {
    const length = user.notes[index].length;
    await wait(650);
    try {
      await user.fetchNotes(index);
    } catch (err) {
      const status = err?.response?.status ?? err?.status ?? err?.code;
      error = [429, 461].includes(Number(status)) ? 'rate' : 'request';
      break;
    }
    if (!user.loggedIn) return { error: 'login' };
    if (user.userNoteFetchingStatus?.[index] === 'rejected') {
      error = 'request';
      break;
    }
    const after = user.noteQueries[index];
    if (after.hasMore && (user.notes[index].length < length ||
        (after.cursor === cursor && after.page === page))) {
      stalled = true;
      break;
    }
    cursor = after.cursor;
    page = after.page;
  }

  const notes = user.notes[index];
  const rows = notes.slice(offset).map((entry) => {
    const card = entry.noteCard ?? entry.note_card ?? entry;
    const id = entry.id || card.noteId || card.note_id;
    const token = entry.xsecToken || entry.xsec_token || card.xsecToken || card.xsec_token;
    return {
      id,
      title: card.displayTitle || card.display_title || card.title || '',
      author: card.user?.nickname || '',
      likes: card.interactInfo?.likedCount ?? card.interact_info?.liked_count ?? null,
      type: card.type || '',
      url: 'https://www.xiaohongshu.com/explore/' + encodeURIComponent(id) +
        (token ? '?xsec_token=' + encodeURIComponent(token) + '&xsec_source=pc_user' : ''),
    };
  });
  return { rows, offset: notes.length, more: user.noteQueries[index].hasMore,
    cursor, page, stalled, error };
}
