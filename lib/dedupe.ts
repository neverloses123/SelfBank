export type MatchableTransaction = {
  title: string;
  amount: number;
  date: string;
  type: "expense" | "income";
  source: string;
};

const merchantNoise = /(股份有限公司|有限公司|企業社|分公司|門市部|門市|信用卡消費|簽帳消費|一般消費|消費款|交易)/g;

export function normalizeMerchant(value: string) {
  return value
    .normalize("NFKC")
    .toUpperCase()
    .replace(merchantNoise, "")
    .replace(/[^0-9A-Z\u3400-\u9FFF]/g, "");
}

function dayDistance(a: string, b: string) {
  const left = Date.parse(`${a}T00:00:00Z`);
  const right = Date.parse(`${b}T00:00:00Z`);
  if (!Number.isFinite(left) || !Number.isFinite(right)) return Infinity;
  return Math.abs(left - right) / 86_400_000;
}

function bigrams(value: string) {
  if (value.length < 2) return [value];
  return Array.from({ length: value.length - 1 }, (_, index) => value.slice(index, index + 2));
}

export function merchantSimilarity(a: string, b: string) {
  const left = normalizeMerchant(a);
  const right = normalizeMerchant(b);
  if (!left || !right) return 0;
  if (left === right) return 1;
  if (Math.min(left.length, right.length) >= 3 && (left.includes(right) || right.includes(left))) return 0.95;
  const available = bigrams(right);
  let matches = 0;
  for (const gram of bigrams(left)) {
    const index = available.indexOf(gram);
    if (index >= 0) { matches += 1; available.splice(index, 1); }
  }
  return (2 * matches) / (bigrams(left).length + bigrams(right).length);
}

export function isDuplicateTransaction(candidate: MatchableTransaction, existing: MatchableTransaction) {
  if (candidate.type !== existing.type || Math.abs(candidate.amount - existing.amount) > 0.01) return false;

  const days = dayDistance(candidate.date, existing.date);
  const similarity = merchantSimilarity(candidate.title, existing.title);

  // 同日、同金額、同店家的重複匯入。
  if (days === 0 && similarity >= 0.9) return true;

  // 銀行入帳日可能比載具發票晚；只對雲端發票放寬到三天。
  const carrierPair = candidate.source === "雲端發票" || existing.source === "雲端發票";
  return carrierPair && days <= 3 && similarity >= 0.82;
}
