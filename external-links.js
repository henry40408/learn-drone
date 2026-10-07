// 外部連結在新分頁開啟
document.querySelectorAll('a[href^="http"]').forEach((a) => {
  if (a.hostname !== location.hostname) {
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
  }
});
