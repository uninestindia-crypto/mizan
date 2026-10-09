These are real results filings published by NSE, trimmed. Every kept line is unchanged. Only the contexts, units and the facts the tests read were kept (no segment or cash-flow lines), so the SHA-256 of a trimmed file differs from the SHA-256 of the file NSE published. Fetched once, politely, on 2026-10-07 with the app's own filings client. Never fetch in a test.

| File | Company | Period | Source |
|---|---|---|---|
| `tcs_2024-09-30_consolidated_trimmed.xml` | Tata Consultancy Services, consolidated | quarter ended 30 Sep 2024, balance sheet at 30 Sep 2024 | https://nsearchives.nseindia.com/corporate/xbrl/INDAS_112733_1265368_10102024065944.xml (original SHA-256 `af60aa3f911a770c6b3f7fd33b6d064d0c1c1326373536e5b2262a4194ccd461`) |
| `tcs_2024-12-31_consolidated_trimmed.xml` | Tata Consultancy Services, consolidated | quarter ended 31 Dec 2024, no balance sheet | https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117182_1341298_09012025093940.xml (original `6bdcf64f71d2e67af2dd6cb2b1e223ec71e0129d72930aad788c5e425d6e2160`) |
| `tatasteel_2024-09-30_consolidated_trimmed.xml` | Tata Steel, consolidated | quarter ended 30 Sep 2024, balance sheet with borrowings and a minority share | https://nsearchives.nseindia.com/corporate/xbrl/INDAS_114281_1299108_06112024065731.xml (original `1cac16efc9247cb7e92b2a52f90dd3e8d15417d01b9b48a49371b839d3fde8ab`) |
| `hdfcbank_2024-09-30_consolidated_trimmed.xml` | HDFC Bank, consolidated | quarter ended 30 Sep 2024, banking layout (not read) | https://nsearchives.nseindia.com/corporate/xbrl/BANKING_112946_1281172_20102024121424.xml (original `da358344c0306c706f82266a18330cfc5ce3291bd44bd61b3d02a05def0c475d`) |

Each filing's own figures tie out: total income less expenses equals profit before exceptional items; adding exceptional items gives profit before tax; less tax (and plus the share of associates) gives profit for the period; owners plus minority equals profit for the period; total equity plus liabilities equals total assets. The tests assert these on the real tags.

The filings declare the year-to-date context `FourD` with the quarter's dates and give the true start in a `DateOfStartOfReportingPeriod` fact; the reader in `src/quant_system/shariah/filings/xbrl.py` resolves that.
