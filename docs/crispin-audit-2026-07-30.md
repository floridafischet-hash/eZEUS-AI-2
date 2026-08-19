# Crispin document audit — 2026-07-30

Read-only audit of all 72 documents in the Crispin Paperless instance.

## Result

- 68 documents have a stored invoice amount.
- Every stored invoice amount matches the amount selected from the OCR text.
- Two invoices are missing an amount:
  - Document 65, invoice 1356: `Gesamtrechnungsbetrag 208,74 €`
  - Document 69, invoice 1735: `Gesamtrechnungsbetrag 115,97 €`
- Two receipts are missing an invoice/reference number:
  - Document 57: `Beleg-Nr. 32002`
  - Document 59: `Beleg-Nr. 31956`
- Documents 61 and 68 are cash-deposit self-receipts, not invoices. Their amounts
  of 3,500.00 EUR and 500.00 EUR should not be copied into the invoice-amount
  field automatically.
- All 72 documents are assigned the document type `Eingangsrechnung`. Documents
  61 and 68 should be reviewed and assigned a more suitable type.
- Duplicate invoice-number warnings require human review:
  - `20JJ03047`: documents 14 and 63
  - `20JJ03056`: documents 23 and 66

## Learned extraction variants

The automatic template now recognizes:

- `Gesamtrechnungsbetrag` as a gross invoice-total label.
- `Beleg-Nr.` / `Beleg-Nummer` as receipt reference labels.

Both variants are covered by regression tests. The cash-deposit wording remains
excluded deliberately so that a deposit amount is not misclassified as an
invoice total.
