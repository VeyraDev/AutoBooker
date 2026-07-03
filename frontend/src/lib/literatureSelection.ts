export function mergeLiteratureSelection(
  current: ReadonlySet<string>,
  pageKeys: Iterable<string>,
): Set<string> {
  const next = new Set(current);
  for (const key of pageKeys) next.add(key);
  return next;
}
