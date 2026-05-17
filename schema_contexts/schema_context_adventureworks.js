// AdventureWorks2019 schema — sourced from the live PostgreSQL database.
// Edit this file to update the AI's schema knowledge; the HTML loads it at startup.
// Prompt caching (cache_control: ephemeral) is applied in the HTML so this block
// is only billed once per cache TTL (~5 min), not on every message.
//
// Naming conventions in this PostgreSQL port:
//   schemas  : lowercase, no underscores  (sales, humanresources, production …)
//   tables   : lowercase snake_case       (sales_order_header, product_subcategory …)
//   columns  : lowercase, no underscores  (salesorderid, orderdate, businessentityid …)

const ADVENTUREWORKS_SCHEMA_CONTEXT = `## Schema — AdventureWorks2019 (PostgreSQL)

IMPORTANT: Always use schema-qualified names exactly as shown below.
Example: sales.sales_order_header, production.product, humanresources.employee

---

### sales.sales_order_header
- salesorderid (bigint, PK), revisionnumber, orderdate, duedate, shipdate
- status (bigint): 1=In process, 2=Approved, 3=Backordered, 4=Rejected, 5=Shipped, 6=Cancelled
- onlineorderflag (boolean), salesordernumber (text)
- purchaseordernumber, accountnumber
- customerid (bigint, FK → sales.customer)
- salespersonid (double precision, FK → sales.sales_person, nullable)
- territoryid (bigint, FK → sales.sales_territory)
- billtoaddressid (bigint, FK → person.address)
- shiptoaddressid (bigint, FK → person.address)
- shipmethodid (bigint, FK → purchasing.ship_method)
- creditcardid (double precision, FK → sales.credit_card, nullable)
- creditcardapprovalcode, currencyrateid (double precision, nullable)
- subtotal, taxamt, freight, totaldue (all double precision)
- comment, rowguid, modifieddate
- Date range: 2011-05-31 to 2014-06-30

### sales.sales_order_detail
- salesorderid (bigint, FK → sales.sales_order_header), salesorderdetailid (bigint, PK)
- carriertrackingnumber (text, nullable)
- orderqty (bigint), productid (bigint, FK → production.product)
- specialofferid (bigint, FK → sales.special_offer)
- unitprice (double precision), unitpricediscount (double precision, default 0)
- linetotal (double precision, computed = unitprice*(1−unitpricediscount)*orderqty)
- rowguid, modifieddate

### sales.customer
- customerid (bigint, PK)
- personid (double precision, FK → person.person, nullable — null for store/B2B customers)
- storeid (double precision, FK → sales.store, nullable — null for individual/B2C customers)
- territoryid (bigint, FK → sales.sales_territory)
- accountnumber (text), rowguid, modifieddate

### sales.store
- businessentityid (bigint, PK, FK → person.business_entity)
- name (text), salespersonid (bigint, FK → sales.sales_person)
- demographics (text), rowguid, modifieddate

### sales.sales_person
- businessentityid (bigint, PK, FK → humanresources.employee)
- territoryid (double precision, FK → sales.sales_territory, nullable)
- salesquota (double precision, nullable)
- bonus (bigint), commissionpct (double precision)
- salesytd (double precision), saleslastyear (double precision)
- rowguid, modifieddate

### sales.sales_territory
- territoryid (bigint, PK), name (text)
- countryregioncode (text, FK → person.country_region)
- group (text): North America, Europe, Pacific
- salesytd (double precision), saleslastyear (double precision)
- costytd (bigint), costlastyear (bigint)
- rowguid, modifieddate
- Territories: Northwest, Northeast, Central, Southwest, Southeast, Canada, France, Germany, Australia, United Kingdom

### sales.sales_territory_history
- businessentityid (bigint, FK → sales.sales_person)
- territoryid (bigint, FK → sales.sales_territory)
- startdate, enddate (text), rowguid, modifieddate

### sales.sales_person_quota_history
- businessentityid (bigint, FK → sales.sales_person)
- quotadate (text), salesquota (bigint), rowguid, modifieddate

### sales.special_offer
- specialofferid (bigint, PK), description (text), discountpct (double precision)
- type (text): No Discount, Volume Discount, Discontinued Product, Seasonal Discount, Excess Inventory, Mountain-100 Clearance
- category (text), startdate, enddate (text), minqty (bigint), maxqty (double precision, nullable)
- rowguid, modifieddate

### sales.special_offer_product
- specialofferid (bigint, FK → sales.special_offer)
- productid (bigint, FK → production.product)
- rowguid, modifieddate

### sales.sales_reason
- salesreasonid (bigint, PK), name (text), reasontype (text), modifieddate

### sales.sales_order_header_sales_reason
- salesorderid (bigint, FK → sales.sales_order_header)
- salesreasonid (bigint, FK → sales.sales_reason), modifieddate

### sales.credit_card
- creditcardid (bigint, PK), cardtype (text), cardnumber (bigint)
- expmonth (bigint), expyear (bigint), modifieddate

### sales.person_credit_card
- businessentityid (bigint, FK → person.person)
- creditcardid (bigint, FK → sales.credit_card), modifieddate

### sales.currency
- currencycode (text, PK), name (text), modifieddate

### sales.currency_rate
- currencyrateid (bigint, PK), currencyratedate (text)
- fromcurrencycode (text), tocurrencycode (text)
- averagerate (double precision), endofdayrate (double precision), modifieddate

### sales.country_region_currency
- countryregioncode (text), currencycode (text), modifieddate

### sales.sales_tax_rate
- salestaxrateid (bigint, PK), stateprovinceid (bigint, FK → person.state_province)
- taxtype (bigint), taxrate (double precision), name (text), rowguid, modifieddate

### sales.shopping_cart_item
- shoppingcartitemid (bigint, PK), shoppingcartid (bigint)
- quantity (bigint), productid (bigint, FK → production.product)
- datecreated (text), modifieddate

---

### production.product
- productid (bigint, PK), name (text), productnumber (text)
- makeflag (boolean: true=manufactured in-house), finishedgoodsflag (boolean: true=sold to customers)
- color (text, nullable), safetystocklevel (bigint), reorderpoint (bigint)
- standardcost (double precision), listprice (double precision)
- size (text, nullable), sizeunitmeasurecode (text, nullable, FK → production.unit_measure)
- weightunitmeasurecode (text, nullable, FK → production.unit_measure), weight (double precision, nullable)
- daystomanufacture (bigint)
- productline (text, nullable): R=Road, M=Mountain, T=Touring, S=Standard
- class (text, nullable): H=High, M=Medium, L=Low
- style (text, nullable): W=Womens, M=Mens, U=Universal
- productsubcategoryid (double precision, nullable, FK → production.product_subcategory)
- productmodelid (double precision, nullable, FK → production.product_model)
- sellstartdate, sellenddate (text), discontinueddate (nullable)
- rowguid, modifieddate

### production.product_subcategory
- productsubcategoryid (bigint, PK)
- productcategoryid (bigint, FK → production.product_category)
- name (text), rowguid, modifieddate

### production.product_category
- productcategoryid (bigint, PK), name (text): Bikes, Components, Clothing, Accessories
- rowguid, modifieddate

### production.product_model
- productmodelid (bigint, PK), name (text)
- catalogdescription (text, nullable), instructions (text, nullable)
- rowguid, modifieddate

### production.product_cost_history
- productid (bigint, FK → production.product), startdate (text), enddate (text)
- standardcost (double precision), modifieddate

### production.product_list_price_history
- productid (bigint, FK → production.product), startdate (text), enddate (text)
- listprice (double precision), modifieddate

### production.product_inventory
- productid (bigint, FK → production.product)
- locationid (bigint, FK → production.location)
- shelf (text), bin (bigint), quantity (bigint), rowguid, modifieddate

### production.location
- locationid (bigint, PK), name (text), costrate (double precision)
- availability (bigint), modifieddate

### production.unit_measure
- unitmeasurecode (text, PK), name (text), modifieddate

### production.work_order
- workorderid (bigint, PK), productid (bigint, FK → production.product)
- orderqty (bigint), stockedqty (bigint), scrappedqty (bigint)
- startdate, enddate, duedate (text)
- scrapreasonid (double precision, nullable, FK → production.scrap_reason)
- modifieddate

### production.work_order_routing
- workorderid (bigint, FK → production.work_order), productid (bigint)
- operationsequence (bigint), locationid (bigint, FK → production.location)
- scheduledstartdate, scheduledenddate, actualstartdate, actualenddate (text)
- actualresourcehrs (double precision, nullable)
- plannedcost (double precision), actualcost (double precision, nullable)
- modifieddate

### production.scrap_reason
- scrapreasonid (bigint, PK), name (text), modifieddate

### production.transaction_history
- transactionid (bigint, PK), productid (bigint, FK → production.product)
- referenceorderid (bigint), referenceorderlineid (bigint), transactiondate (text)
- transactiontype (text): W=WorkOrder, S=SalesOrder, P=PurchaseOrder
- quantity (bigint), actualcost (double precision), modifieddate

### production.bill_of_materials
- billofmaterialsid (bigint, PK)
- productassemblyid (double precision, nullable, FK → production.product)
- componentid (bigint, FK → production.product)
- startdate, enddate (text), unitmeasurecode (text, FK → production.unit_measure)
- bomlevel (bigint), perassemblyqty (bigint), modifieddate

### production.product_review
- productreviewid (bigint, PK), productid (bigint, FK → production.product)
- reviewername (text), reviewdate (text), emailaddress (text)
- rating (bigint), comments (text), modifieddate

### production.product_description
- productdescriptionid (bigint, PK), description (text), rowguid, modifieddate

### production.product_model_product_description_culture
- productmodelid (bigint, FK → production.product_model)
- productdescriptionid (bigint, FK → production.product_description)
- cultureid (text, FK → production.culture), modifieddate

### production.culture
- cultureid (text, PK), name (text), modifieddate

---

### purchasing.vendor
- businessentityid (bigint, PK, FK → person.business_entity)
- accountnumber (text), name (text)
- creditrating (bigint): 1=Superior, 2=Excellent, 3=Above average, 4=Average, 5=Below average
- preferredvendorstatus (boolean), activeflag (boolean)
- purchasingwebserviceurl (text, nullable), modifieddate

### purchasing.product_vendor
- productid (bigint, FK → production.product)
- businessentityid (bigint, FK → purchasing.vendor)
- averageleadtime (bigint), standardprice (double precision)
- lastreceiptcost (double precision, nullable), lastreceiptdate (text, nullable)
- minorderqty (bigint), maxorderqty (bigint), onorderqty (double precision, nullable)
- unitmeasurecode (text, FK → production.unit_measure), modifieddate

### purchasing.purchase_order_header
- purchaseorderid (bigint, PK), revisionnumber (bigint)
- status (bigint): 1=Pending, 2=Approved, 3=Rejected, 4=Complete
- employeeid (bigint, FK → humanresources.employee)
- vendorid (bigint, FK → purchasing.vendor)
- shipmethodid (bigint, FK → purchasing.ship_method)
- orderdate, shipdate (text)
- subtotal, taxamt, freight, totaldue (double precision), modifieddate

### purchasing.purchase_order_detail
- purchaseorderid (bigint, FK → purchasing.purchase_order_header)
- purchaseorderdetailid (bigint, PK), duedate (text)
- orderqty (bigint), productid (bigint, FK → production.product)
- unitprice, linetotal (double precision)
- receivedqty, rejectedqty, stockedqty (bigint), modifieddate

### purchasing.ship_method
- shipmethodid (bigint, PK), name (text)
- shipbase (double precision), shiprate (double precision)
- rowguid, modifieddate

---

### person.person
- businessentityid (bigint, PK, FK → person.business_entity)
- persontype (text): EM=Employee, IN=Individual Customer, SC=StoreContact, SP=SalesPerson, VC=VendorContact, GC=GeneralContact
- namestyle (boolean), title (text, nullable)
- firstname (text), middlename (text, nullable), lastname (text), suffix (text, nullable)
- emailpromotion (bigint): 0=None, 1=AdventureWorks only, 2=All partners
- additionalcontactinfo (text, nullable), demographics (text, nullable)
- rowguid, modifieddate

### person.business_entity
- businessentityid (bigint, PK), rowguid, modifieddate

### person.address
- addressid (bigint, PK), addressline1 (text), addressline2 (text, nullable)
- city (text), stateprovinceid (bigint, FK → person.state_province)
- postalcode (text), spatiallocation (text, nullable), rowguid, modifieddate

### person.business_entity_address
- businessentityid (bigint, FK → person.business_entity)
- addressid (bigint, FK → person.address)
- addresstypeid (bigint, FK → person.address_type)
- rowguid, modifieddate

### person.address_type
- addresstypeid (bigint, PK), name (text): Billing, Home, Main Office, Primary, Shipping, Archive
- rowguid, modifieddate

### person.state_province
- stateprovinceid (bigint, PK), stateprovincecode (text)
- countryregioncode (text, FK → person.country_region)
- isonlystateprovinceflag (boolean), name (text)
- territoryid (bigint, FK → sales.sales_territory)
- rowguid, modifieddate

### person.country_region
- countryregioncode (text, PK), name (text), modifieddate

### person.email_address
- businessentityid (bigint, FK → person.person), emailaddressid (bigint)
- emailaddress (text, nullable), rowguid, modifieddate

### person.person_phone
- businessentityid (bigint, FK → person.person)
- phonenumber (text), phonenumbertypeid (bigint, FK → person.phone_number_type)
- modifieddate

### person.phone_number_type
- phonenumbertypeid (bigint, PK), name (text): Cell, Home, Work, modifieddate

### person.contact_type
- contacttypeid (bigint, PK), name (text), modifieddate

### person.business_entity_contact
- businessentityid (bigint, FK → person.business_entity)
- personid (bigint, FK → person.person)
- contacttypeid (bigint, FK → person.contact_type)
- rowguid, modifieddate

---

### humanresources.employee
- businessentityid (bigint, PK, FK → person.person)
- nationalidnumber (bigint), loginid (text)
- organizationnode (text), organizationlevel (double precision, nullable)
- jobtitle (text), birthdate (text)
- maritalstatus (text): M=Married, S=Single
- gender (text): M=Male, F=Female
- hiredate (text), salariedflag (boolean)
- vacationhours (bigint), sickleavehours (bigint)
- currentflag (boolean), rowguid, modifieddate

### humanresources.employee_department_history
- businessentityid (bigint, FK → humanresources.employee)
- departmentid (bigint, FK → humanresources.department)
- shiftid (bigint, FK → humanresources.shift)
- startdate (text), enddate (text, nullable), modifieddate

### humanresources.department
- departmentid (bigint, PK), name (text), groupname (text), modifieddate
- Groups: Executive General and Administration, Inventory Management, Manufacturing, Quality Assurance, Research and Development, Sales and Marketing

### humanresources.shift
- shiftid (bigint, PK), name (text): Day, Evening, Night
- starttime (text), endtime (text), modifieddate

### humanresources.employee_pay_history
- businessentityid (bigint, FK → humanresources.employee)
- ratechangedate (text), rate (double precision)
- payfrequency (bigint): 1=Monthly, 2=Biweekly
- modifieddate

### humanresources.job_candidate
- jobcandidateid (bigint, PK)
- businessentityid (double precision, nullable, FK → humanresources.employee)
- resume (text, nullable), modifieddate

---

## Useful Views (prefix with schema name)
- humanresources.v_employee — employee with name, contact, address details joined
- humanresources.v_employee_department — employee with current department and group
- humanresources.v_employee_department_history — employee with all department history
- sales.v_individual_customer — individual customers with person details
- sales.v_sales_person — salesperson with name, territory, quota, YTD
- sales.v_sales_person_sales_by_fiscal_years — pivot of sales by year per person
- sales.v_store_with_addresses — stores with address details
- sales.v_store_with_contacts — stores with contact person details
- production.v_product_and_description — products with description by culture
- production.v_product_model_catalog_description — product model catalog info

---

## Key Relationships
- sales_order_detail → sales_order_header (salesorderid)
- sales_order_detail → production.product (productid)
- sales_order_detail → sales.special_offer via special_offer_product (specialofferid + productid)
- sales_order_header → sales.customer (customerid)
- sales_order_header → sales.sales_territory (territoryid)
- sales_order_header → sales.sales_person (salespersonid) — nullable
- sales.customer → person.person (personid) — null for B2B/store customers
- sales.customer → sales.store (storeid) — null for B2C/individual customers
- production.product → production.product_subcategory → production.product_category
- production.product → production.product_model
- production.product ↔ purchasing.vendor via purchasing.product_vendor
- humanresources.employee → person.person (same businessentityid)
- sales.sales_person → humanresources.employee → person.person (same businessentityid chain)
- sales.store → sales.sales_person (salespersonid)
- person.person → person.address via person.business_entity_address (many addresses per entity)
- person.state_province → sales.sales_territory (territoryid)`;
