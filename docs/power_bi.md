# Power BI Desktop check

The PBIP includes separate Sales (one order) and Items (one order item) facts. Calendar and customer State filter both; Seller and Category filter Items. All dimension keys are unique and relationships filter one way. Do not link order and item facts directly or sum order value after joining items.

Customer/cohort tables retain their own analytical grain and do not inherit unrelated order filters. Calendar covers complete calendar years. GMV MoM uses DATEADD; YTD uses TOTALYTD. MoM is shown only for one selected calendar month. August is descriptive because tail completeness is uncertain.

Run from the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/build_powerbi.py --reports-dir "$PWD/reports"
```

Open dashboards/powerbi/Olist/Olist.pbip in Desktop. Refresh. Check BRL 13,221,498 GMV and 96,478 delivered orders at the full date range. Inspect model relationships. Select a month in the monthly table and verify MoM against monthly_sales.csv. Right-click RJ in the state chart, Drill through > Investigate sellers serving this state. Verify seller order counts and category/state filters; whole-order lateness is shared across multi-seller orders and is not seller fault.

JSON schemas and field references are checked by pytest. Run the Desktop refresh and interaction checks above on your machine before publishing.
