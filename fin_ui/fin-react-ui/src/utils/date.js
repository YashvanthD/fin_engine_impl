// ...existing code...
export function getDefaultEndDate() {
  const now = new Date();
  now.setHours(now.getHours() + 1);
  return now.toISOString().slice(0, 16).replace('T', ' '); // 'YYYY-MM-DD HH:mm'
}

export function getTimeLeft(endDate) {
  if (!endDate) return '';
  const now = new Date();
  let end;
  if (typeof endDate === 'string' && endDate.length > 10) {
    end = new Date(endDate.replace(' ', 'T'));
  } else {
    end = new Date(endDate);
  }
  const diffMs = end - now;
  if (diffMs <= 0) return 'Expired';
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin} min left`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr left`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay} day${diffDay > 1 ? 's' : ''} left`;
}
// ...existing code...
