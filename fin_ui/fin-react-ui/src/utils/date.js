// ...existing code...
export function getDefaultEndDate() {
  const now = new Date();
  now.setHours(now.getHours() + 1);
  return now.toISOString().slice(0, 16).replace('T', ' '); // 'YYYY-MM-DD HH:mm'
}
// ...existing code...

