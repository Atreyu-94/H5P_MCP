// Scalar rules are independent of Lumi, storage, and network access.
function scalarErrors(entry, value) {
  const errors = [];
  if (entry.type === 'text') {
    if (typeof value !== 'string') return ['expected text'];
    if (entry.widget !== 'html' && entry.maxLength != null && value.length > entry.maxLength)
      errors.push(`maximum length ${entry.maxLength}`);
    if (entry.regexp) {
      try {
        if (!new RegExp(entry.regexp.pattern, entry.regexp.modifiers || '').test(value)) errors.push('text does not match regexp');
      } catch { errors.push('unsupported or invalid schema regexp'); }
    }
  }
  if (entry.type === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) return ['expected finite number'];
    if (entry.min != null && value < entry.min) errors.push(`minimum ${entry.min}`);
    if (entry.max != null && value > entry.max) errors.push(`maximum ${entry.max}`);
    if (entry.decimals != null) {
      // Decimal representation avoids false failures from binary multiplication.
      const [mantissa, exponent = '0'] = String(value).toLowerCase().split('e');
      const digits = Math.max(0, (mantissa.split('.')[1] || '').length - Number(exponent));
      if (digits > entry.decimals) errors.push(`maximum ${entry.decimals} decimal digits`);
    }
  }
  return errors;
}
module.exports = {scalarErrors};
