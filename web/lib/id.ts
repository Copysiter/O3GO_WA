export function generateId({ length = 8 }: { length?: number } = {}): string {
  const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const alphabetLength = alphabet.length;
  let result = "";
  for (let i = 0; i < length; i++) {
    const index = Math.floor(Math.random() * alphabetLength);
    result += alphabet[index];
  }
  return result;
}


