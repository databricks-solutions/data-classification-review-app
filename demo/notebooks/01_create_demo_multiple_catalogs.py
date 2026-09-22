# Databricks notebook source
# DBTITLE 1,Energy Company Data Model - Overview
# MAGIC %md
# MAGIC # Energy Company Data Model
# MAGIC
# MAGIC **5 Catalogs** | **13 Schemas** | **50 Tables** | **40% contain PII**
# MAGIC
# MAGIC | Catalog | Business Unit | Schemas |
# MAGIC | --- | --- | --- |
# MAGIC | `generation` | Power Generation | assets, operations, environmental |
# MAGIC | `energy_trading` | Trading & Markets | market_data, positions, risk_management |
# MAGIC | `retail_customers` | Customer Supply | customer_management, metering, billing |
# MAGIC | `grid_operations` | Distribution Network | network_assets, field_operations |
# MAGIC | `corporate` | Shared Services | human_resources, finance, compliance |
# MAGIC
# MAGIC Columns marked with `PII` in comments are expected to be flagged by Databricks Data Classification.

# COMMAND ----------

# DBTITLE 1,Parameters
dbutils.widgets.text("enable_dc", "true", "Enable Data Classification")

# COMMAND ----------

# DBTITLE 1,Drop All Catalogs (Cleanup)
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CLEANUP: Drop all catalogs created in this notebook
# MAGIC -- Run this cell to reset the environment before re-executing
# MAGIC -- ============================================================
# MAGIC
# MAGIC DROP CATALOG IF EXISTS dc_demo_generation CASCADE;
# MAGIC DROP CATALOG IF EXISTS dc_demo_energy_trading CASCADE;
# MAGIC DROP CATALOG IF EXISTS dc_demo_retail_customers CASCADE;
# MAGIC DROP CATALOG IF EXISTS dc_demo_grid_operations CASCADE;
# MAGIC DROP CATALOG IF EXISTS dc_demo_corporate CASCADE;

# COMMAND ----------

# DBTITLE 1,Catalog 1: generation
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CATALOG: generation
# MAGIC -- Power generation assets, operations, and environmental compliance
# MAGIC -- ============================================================
# MAGIC
# MAGIC CREATE CATALOG IF NOT EXISTS dc_demo_generation;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_generation.assets;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_generation.operations;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_generation.environmental;
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_generation.assets
# MAGIC -- Core registry of generation infrastructure
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.assets.power_plants (
# MAGIC   plant_id INT NOT NULL COMMENT 'Unique plant identifier',
# MAGIC   name STRING NOT NULL COMMENT 'Plant name',
# MAGIC   fuel_type STRING NOT NULL COMMENT 'Primary fuel determines EU ETS carbon allowance obligations (gas and coal plants must surrender allowances annually; nuclear has none) and sets the applicable heat rate benchmark for efficiency monitoring',
# MAGIC   capacity_mw DECIMAL(10,2) COMMENT 'Nameplate capacity under design conditions; actual output is lower due to availability constraints and ambient temperature effects; reported to system operators for capacity market auctions and REMIT registration',
# MAGIC   location STRING COMMENT 'Site address',
# MAGIC   city STRING,
# MAGIC   country STRING,
# MAGIC   latitude DOUBLE,
# MAGIC   longitude DOUBLE,
# MAGIC   commissioned_date DATE,
# MAGIC   decommission_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'active = fully dispatchable; standby = retained for peak demand and capacity market obligations but not currently generating; decommissioned = permanently retired and notified to system operator and regulator',
# MAGIC   CONSTRAINT pk_power_plants PRIMARY KEY (plant_id)
# MAGIC ) COMMENT 'Registry of thermal power generation plants; source of truth for REMIT capacity notifications and regulatory asset management; renewable sites are tracked separately in dc_demo_generation.assets.renewable_sites due to their distinct fuel-free, intermittent operating characteristics';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.assets.generation_units (
# MAGIC   unit_id INT NOT NULL COMMENT 'Unique generation unit identifier',
# MAGIC   plant_id INT NOT NULL COMMENT 'FK to power_plants',
# MAGIC   unit_type STRING NOT NULL COMMENT 'turbine, boiler, reactor, engine',
# MAGIC   capacity_mw DECIMAL(10,2),
# MAGIC   efficiency_pct DECIMAL(5,2) COMMENT 'Ratio of electrical output to fuel energy input; CCGT typically 55-60%, coal 35-42%, nuclear 33-37%; deteriorates with age and between major overhauls; used to benchmark fuel procurement volumes and forecast heat rate',
# MAGIC   last_overhaul_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'operational = available for dispatch; maintenance = unavailable due to planned overhaul or forced outage; retired = permanently offline while the parent plant may continue operating with remaining units',
# MAGIC   CONSTRAINT pk_generation_units PRIMARY KEY (unit_id),
# MAGIC   CONSTRAINT fk_units_plant FOREIGN KEY (plant_id) REFERENCES dc_demo_generation.assets.power_plants(plant_id)
# MAGIC ) COMMENT 'Granular asset units within plants (turbines, boilers, reactors, engines); a single plant may have 2-8 units; all production logs, maintenance orders, and outage events are recorded at unit level for accurate performance attribution and REMIT reporting';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.assets.renewable_sites (
# MAGIC   site_id INT NOT NULL COMMENT 'Unique renewable site identifier',
# MAGIC   name STRING NOT NULL,
# MAGIC   technology STRING NOT NULL COMMENT 'wind_onshore, wind_offshore, solar_pv, hydro',
# MAGIC   capacity_mw DECIMAL(10,2),
# MAGIC   num_units INT COMMENT 'Number of turbines or panel arrays',
# MAGIC   latitude DOUBLE,
# MAGIC   longitude DOUBLE,
# MAGIC   grid_connection_point STRING COMMENT 'Reference to the physical substation bus bar where this site connects to the network; connection capacity is capped by the entry in dc_demo_grid_operations.network_assets.grid_connection_points',
# MAGIC   commissioned_date DATE,
# MAGIC   status STRING NOT NULL,
# MAGIC   CONSTRAINT pk_renewable_sites PRIMARY KEY (site_id)
# MAGIC ) COMMENT 'Wind, solar, and hydro sites tracked separately from thermal plants; output is weather-dependent and intermittent; no fuel cost or EU ETS obligation; Renewable Energy Guarantee of Origin (REGO) certificates are issued per MWh generated and sold to customers on green tariffs';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_generation.operations
# MAGIC -- Operational data: production, maintenance, fuel, outages
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.operations.production_logs (
# MAGIC   log_id BIGINT NOT NULL COMMENT 'Unique log entry',
# MAGIC   unit_id INT NOT NULL COMMENT 'FK to generation_units',
# MAGIC   timestamp TIMESTAMP NOT NULL COMMENT 'Measurement timestamp',
# MAGIC   output_mwh DECIMAL(10,3) COMMENT 'Net energy exported to grid after auxiliary consumption; the basis for revenue settlement with the national grid balancing mechanism; summed daily for REMIT generation availability reports',
# MAGIC   availability_pct DECIMAL(5,2) COMMENT 'Proportion of the period the unit was technically capable of generating at full output; 0 = full unplanned outage; values below 100 include partial deratings and planned maintenance windows; key asset KPI tracked against OEM design benchmarks',
# MAGIC   fuel_consumed_tonnes DECIMAL(10,3) COMMENT 'Actual fuel burned in the period; divided by output_mwh yields the heat rate efficiency metric; also the primary input for CO2 emission calculations in dc_demo_generation.environmental.emissions_readings',
# MAGIC   CONSTRAINT pk_production_logs PRIMARY KEY (log_id),
# MAGIC   CONSTRAINT fk_prodlogs_unit FOREIGN KEY (unit_id) REFERENCES dc_demo_generation.assets.generation_units(unit_id)
# MAGIC ) COMMENT 'Primary generation output time-series; used for BSC imbalance settlement, capacity factor KPIs, and heat rate benchmarking; regulators require minimum 13-month data retention for REMIT compliance; actual reads trigger settlement with the national grid balancing mechanism';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.operations.maintenance_orders (
# MAGIC   order_id INT NOT NULL,
# MAGIC   unit_id INT NOT NULL COMMENT 'FK to generation_units',
# MAGIC   order_type STRING NOT NULL COMMENT 'preventive = OEM-scheduled overhaul executed on a fixed interval; corrective = reactive repair triggered by fault detection; emergency = immediate safety or grid stability risk requiring same-day crew dispatch',
# MAGIC   technician_name STRING COMMENT 'Assigned technician full name',
# MAGIC   technician_phone STRING COMMENT 'Technician contact phone number',
# MAGIC   scheduled_date DATE,
# MAGIC   completion_date DATE,
# MAGIC   cost_eur DECIMAL(12,2),
# MAGIC   status STRING NOT NULL COMMENT 'open, in_progress, completed, cancelled',
# MAGIC   CONSTRAINT pk_maintenance_orders PRIMARY KEY (order_id),
# MAGIC   CONSTRAINT fk_maint_unit FOREIGN KEY (unit_id) REFERENCES dc_demo_generation.assets.generation_units(unit_id)
# MAGIC ) COMMENT 'Work orders covering preventive, corrective, and emergency maintenance; emergency orders on units above 100MW must be reported to the system operator within 1 hour as REMIT urgent market messages; records technician PII for dispatch and accountability';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.operations.fuel_inventory (
# MAGIC   inventory_id INT NOT NULL,
# MAGIC   plant_id INT NOT NULL COMMENT 'FK to power_plants',
# MAGIC   fuel_type STRING NOT NULL COMMENT 'gas, coal, oil, uranium',
# MAGIC   quantity_tonnes DECIMAL(12,3) COMMENT 'Current on-site stock in tonnes; divided by the rolling average burn rate from production_logs gives days-of-cover; falling below the regulatory minimum triggers emergency procurement and mandatory regulator notification',
# MAGIC   delivery_date DATE COMMENT 'Date fuel was received on-site; used for stock ageing analysis and supplier delivery SLA tracking',
# MAGIC   supplier_id INT,
# MAGIC   unit_cost_eur DECIMAL(10,2),
# MAGIC   CONSTRAINT pk_fuel_inventory PRIMARY KEY (inventory_id),
# MAGIC   CONSTRAINT fk_fuel_plant FOREIGN KEY (plant_id) REFERENCES dc_demo_generation.assets.power_plants(plant_id)
# MAGIC ) COMMENT 'Physical fuel stock tracker per plant; minimum stock levels are regulated (typically 5-day gas cover, 30-day coal cover); quantity against rolling burn rate from production_logs gives days-of-cover for security-of-supply reporting to regulators';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.operations.outage_events (
# MAGIC   event_id INT NOT NULL,
# MAGIC   unit_id INT NOT NULL COMMENT 'FK to generation_units',
# MAGIC   start_time TIMESTAMP NOT NULL,
# MAGIC   end_time TIMESTAMP,
# MAGIC   cause STRING COMMENT 'mechanical_failure = physical asset breakdown; fuel_supply = gas curtailment or coal delivery shortfall; grid_constraint = transmission bottleneck preventing dispatch; tracked for root-cause trend analysis, insurance claims, and force majeure assessment',
# MAGIC   energy_lost_mwh DECIMAL(10,3),
# MAGIC   is_planned BOOLEAN COMMENT 'True = pre-notified maintenance window agreed with the system operator; false = forced outage; unplanned outages above 100MW trigger mandatory REMIT urgent market message notification within 1 hour',
# MAGIC   CONSTRAINT pk_outage_events PRIMARY KEY (event_id),
# MAGIC   CONSTRAINT fk_outage_unit FOREIGN KEY (unit_id) REFERENCES dc_demo_generation.assets.generation_units(unit_id)
# MAGIC ) COMMENT 'Generation availability log; planned outages above 100MW require 3-day advance notice to the system operator; unplanned outages above 100MW trigger a REMIT urgent market message within 1 hour of occurrence; data feeds capacity market compliance reporting';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_generation.environmental
# MAGIC -- Emissions, permits, and environmental incidents
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.environmental.emissions_readings (
# MAGIC   reading_id BIGINT NOT NULL,
# MAGIC   plant_id INT NOT NULL COMMENT 'FK to power_plants',
# MAGIC   pollutant STRING NOT NULL COMMENT 'CO2 = EU ETS annual surrender obligation with financial penalty for shortfall; NOx and SO2 = Industrial Emissions Directive permit thresholds; particulates = local air quality permit limits; each has distinct measurement methodology and reporting frequency',
# MAGIC   value_tonnes DECIMAL(12,4) COMMENT 'Mass of pollutant emitted during the measurement period in tonnes; aggregated against permits.max_allowed_tonnes for compliance monitoring; exceedance triggers mandatory regulator notification',
# MAGIC   measurement_date DATE NOT NULL,
# MAGIC   CONSTRAINT pk_emissions PRIMARY KEY (reading_id),
# MAGIC   CONSTRAINT fk_emissions_plant FOREIGN KEY (plant_id) REFERENCES dc_demo_generation.assets.power_plants(plant_id)
# MAGIC ) COMMENT 'Measured pollutant emissions used for annual EU ETS allowance surrender reconciliation (CO2) and Industrial Emissions Directive permit compliance (NOx, SO2, particulates); values must be verified by an accredited third party before regulatory submission';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.environmental.permits (
# MAGIC   permit_id INT NOT NULL,
# MAGIC   plant_id INT NOT NULL COMMENT 'FK to power_plants',
# MAGIC   permit_type STRING NOT NULL COMMENT 'emissions, water_discharge, waste_disposal',
# MAGIC   issuing_authority STRING,
# MAGIC   issue_date DATE,
# MAGIC   expiry_date DATE,
# MAGIC   max_allowed_tonnes DECIMAL(12,4) COMMENT 'Annual regulatory emission or discharge threshold set in the permit; any exceedance requires immediate notification to the regulator and may trigger financial penalty, permit revocation, or forced generation curtailment',
# MAGIC   status STRING NOT NULL COMMENT 'active = in full compliance; expired = permit lapsed, renewal required immediately to continue operating legally; revoked = withdrawn by regulator, generation must stop; pending_renewal = application submitted, current permit has a limited grace period',
# MAGIC   CONSTRAINT pk_permits PRIMARY KEY (permit_id),
# MAGIC   CONSTRAINT fk_permits_plant FOREIGN KEY (plant_id) REFERENCES dc_demo_generation.assets.power_plants(plant_id)
# MAGIC ) COMMENT 'Regulatory permits required to legally operate generation assets; generation without a valid active permit is prohibited; permits must be renewed before expiry to avoid forced shutdown; the issuing authority retains the right to audit at any time during the permit lifetime';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_generation.environmental.environmental_incidents (
# MAGIC   incident_id INT NOT NULL,
# MAGIC   plant_id INT NOT NULL COMMENT 'FK to power_plants',
# MAGIC   incident_type STRING NOT NULL COMMENT 'spill/leak = uncontrolled release of fuel, oil, or chemicals into the environment; exceedance = permitted emission threshold breached; wildlife_impact = protected species or habitat disruption near plant; each type carries distinct mandatory notification timelines to different regulators',
# MAGIC   severity STRING NOT NULL COMMENT 'low/medium = internal investigation only, include in next periodic report; high = written notification to regulator within 72 hours; critical = immediate telephone notification and potential unannounced regulatory site visit',
# MAGIC   reporter_name STRING COMMENT 'Name of person who reported the incident',
# MAGIC   reporter_email STRING COMMENT 'Email address of the reporter',
# MAGIC   reported_date DATE NOT NULL,
# MAGIC   resolution_date DATE,
# MAGIC   description STRING,
# MAGIC   CONSTRAINT pk_env_incidents PRIMARY KEY (incident_id),
# MAGIC   CONSTRAINT fk_env_incidents_plant FOREIGN KEY (plant_id) REFERENCES dc_demo_generation.assets.power_plants(plant_id)
# MAGIC ) COMMENT 'Notifiable environmental events at generation sites; critical and high severity incidents must be reported to the national environment agency within 24-72 hours; incident data feeds permit compliance assessment, insurance claims, and annual environmental performance reports';

# COMMAND ----------

# DBTITLE 1,Catalog 2: energy_trading
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CATALOG: energy_trading
# MAGIC -- Trading desk, market positions, and risk management
# MAGIC -- ============================================================
# MAGIC
# MAGIC CREATE CATALOG IF NOT EXISTS dc_demo_energy_trading;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_energy_trading.market_data;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_energy_trading.positions;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_energy_trading.risk_management;
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_energy_trading.market_data
# MAGIC -- Reference/market data: prices, curves, weather
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.market_data.spot_prices (
# MAGIC   price_id BIGINT NOT NULL,
# MAGIC   market STRING NOT NULL COMMENT 'EPEX = European Power Exchange (day-ahead and intraday electricity); NBP = National Balancing Point (UK gas benchmark hub); TTF = Title Transfer Facility (Dutch/EU gas benchmark hub); ICE = Intercontinental Exchange (oil, LNG, carbon)',
# MAGIC   commodity STRING NOT NULL COMMENT 'power, natural_gas, carbon, oil',
# MAGIC   price_eur_mwh DECIMAL(10,4) COMMENT 'Settlement price in EUR/MWh',
# MAGIC   delivery_date DATE NOT NULL,
# MAGIC   hour_of_day INT COMMENT 'Settlement delivery hour for electricity intraday trading only; NULL for gas, carbon, and oil which trade in daily or monthly block contracts rather than hourly delivery slots',
# MAGIC   timestamp TIMESTAMP NOT NULL COMMENT 'Publication timestamp',
# MAGIC   CONSTRAINT pk_spot_prices PRIMARY KEY (price_id)
# MAGIC ) COMMENT 'Exchange-sourced prices used for mark-to-market P&L valuation, settlement of index-linked contracts, and short-term hedging decisions; power prices clear day-ahead; gas prices (NBP/TTF) trade in daily and monthly blocks; feeds daily P&L calculation and trading risk models';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.market_data.forward_curves (
# MAGIC   curve_id BIGINT NOT NULL,
# MAGIC   commodity STRING NOT NULL COMMENT 'power, natural_gas, carbon',
# MAGIC   delivery_period STRING NOT NULL COMMENT 'Tenor bucket notation: M+1 = next calendar month; Q+1 = next calendar quarter; Cal+1 = next full calendar year; determines which forward price bucket applies when marking open trades to market',
# MAGIC   delivery_start DATE,
# MAGIC   delivery_end DATE,
# MAGIC   price_eur_mwh DECIMAL(10,4),
# MAGIC   valuation_date DATE NOT NULL,
# MAGIC   CONSTRAINT pk_forward_curves PRIMARY KEY (curve_id)
# MAGIC ) COMMENT 'Mark-to-market reference prices for open forward positions; rebuilt daily after market close; M+1 through Cal+2 tenors used for IFRS 9 hedge effectiveness testing and structured product pricing; stale curves older than 2 days trigger a data quality alert';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.market_data.weather_forecasts (
# MAGIC   forecast_id BIGINT NOT NULL,
# MAGIC   region STRING NOT NULL COMMENT 'Geographic region for the forecast',
# MAGIC   forecast_date DATE NOT NULL,
# MAGIC   target_date DATE NOT NULL COMMENT 'Date being forecasted',
# MAGIC   temperature_c DECIMAL(5,2),
# MAGIC   wind_speed_ms DECIMAL(5,2),
# MAGIC   solar_irradiance_wm2 DECIMAL(7,2) COMMENT 'Incident solar radiation in W/m²; primary input for solar PV output forecasting; combined with renewable_sites.capacity_mw to project generation volume for next-day trading decisions',
# MAGIC   precipitation_mm DECIMAL(5,2),
# MAGIC   CONSTRAINT pk_weather_forecasts PRIMARY KEY (forecast_id)
# MAGIC ) COMMENT 'Meteorological inputs for demand forecasting (heating/cooling degree days), renewable generation output modelling (wind speed, solar irradiance), and gas sendout projections; updated twice daily from third-party providers; feeds both dispatch optimisation and trading desk risk models';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_energy_trading.positions
# MAGIC -- Trade execution, contracts, counterparties
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.positions.counterparties (
# MAGIC   counterparty_id INT NOT NULL,
# MAGIC   legal_name STRING NOT NULL COMMENT 'Registered legal entity name',
# MAGIC   short_name STRING COMMENT 'Trading desk shorthand',
# MAGIC   tax_id STRING COMMENT 'EU VAT number or US EIN; mandatory for EMIR trade reporting and sanctions screening against OFAC/HMT restricted party lists at onboarding and at each annual review',
# MAGIC   bank_account_iban STRING COMMENT 'Settlement IBAN',
# MAGIC   country STRING,
# MAGIC   credit_rating STRING COMMENT 'S&P or Moody equivalent credit rating; BB- or below triggers enhanced monitoring and increased collateral requirements under the CSA; below CCC prevents new trading; rating drives the Independent Amount threshold in the Credit Support Annex',
# MAGIC   credit_limit_eur DECIMAL(15,2) COMMENT 'Maximum net open exposure approved by the credit team; trades that would breach this threshold are automatically blocked by the trade capture system until the position is reduced or the limit is increased with CRO approval',
# MAGIC   is_active BOOLEAN,
# MAGIC   CONSTRAINT pk_counterparties PRIMARY KEY (counterparty_id)
# MAGIC ) COMMENT 'Authorised trading counterparties; new entities require KYC review and credit team approval before the first trade; credit_limit_eur caps the maximum net open exposure; counterparty records must include a valid LEI or tax_id for EMIR trade reporting';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.positions.trades (
# MAGIC   trade_id BIGINT NOT NULL,
# MAGIC   trader_name STRING NOT NULL COMMENT 'Name of the trader who executed',
# MAGIC   counterparty_id INT NOT NULL COMMENT 'FK to counterparties',
# MAGIC   commodity STRING NOT NULL COMMENT 'power, natural_gas, carbon',
# MAGIC   direction STRING NOT NULL COMMENT 'From the trading desk perspective; buy = long position (profit if price rises above trade price); sell = short position (profit if price falls); combined with volume_mwh determines net position per commodity for limit monitoring',
# MAGIC   volume_mwh DECIMAL(12,3) COMMENT 'Contracted volume in MWh; for gas approx 0.034 MCM per MWh; for carbon one EUA per MWh-equivalent allowance; input to net position and VaR calculations',
# MAGIC   price_eur_mwh DECIMAL(10,4),
# MAGIC   trade_date DATE NOT NULL,
# MAGIC   delivery_start DATE COMMENT 'Start of the physical or financial delivery/settlement reference period; determines which forward curve bucket applies for mark-to-market valuation',
# MAGIC   delivery_end DATE COMMENT 'End of the delivery or settlement reference period; together with delivery_start defines the obligation window and the correct tenor bucket for VaR calculations',
# MAGIC   status STRING NOT NULL COMMENT 'confirmed, settled, cancelled',
# MAGIC   CONSTRAINT pk_trades PRIMARY KEY (trade_id),
# MAGIC   CONSTRAINT fk_trades_cpty FOREIGN KEY (counterparty_id) REFERENCES dc_demo_energy_trading.positions.counterparties(counterparty_id)
# MAGIC ) COMMENT 'Central trade blotter; all confirmed trades are legally binding contracts and must never be deleted; used for real-time P&L, VaR input, position limit monitoring, and mandatory EMIR and REMIT regulatory reporting to trade repositories';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.positions.contracts (
# MAGIC   contract_id INT NOT NULL,
# MAGIC   counterparty_id INT NOT NULL COMMENT 'FK to counterparties',
# MAGIC   contract_type STRING NOT NULL COMMENT 'PPA = Power Purchase Agreement (long-term physical delivery, typically 10-20 years); tolling = capacity lease where buyer provides fuel and seller operates the plant; swap = financial difference contract settling against an index; futures/options = exchange-traded with daily margining',
# MAGIC   signatory_name STRING COMMENT 'Name of the person who signed',
# MAGIC   signatory_email STRING COMMENT 'Email of the signatory',
# MAGIC   start_date DATE,
# MAGIC   end_date DATE,
# MAGIC   notional_value_eur DECIMAL(15,2) COMMENT 'Total financial exposure over the contract lifetime; consumed against counterparty credit_limit_eur for headroom calculations; contracts exceeding €20M require board approval under the Treasury Policy',
# MAGIC   status STRING NOT NULL COMMENT 'active, expired, terminated',
# MAGIC   CONSTRAINT pk_contracts PRIMARY KEY (contract_id),
# MAGIC   CONSTRAINT fk_contracts_cpty FOREIGN KEY (counterparty_id) REFERENCES dc_demo_energy_trading.positions.counterparties(counterparty_id)
# MAGIC ) COMMENT 'Long-term structured contracts defining the framework under which individual trades are executed; PPAs and tolling agreements are disclosed as long-term commitments in IFRS financial statements; contracts above €20M require board-level approval under the Treasury Policy';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_energy_trading.risk_management
# MAGIC -- Portfolio risk, credit exposure, limit monitoring
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.risk_management.var_reports (
# MAGIC   report_id INT NOT NULL,
# MAGIC   desk STRING NOT NULL COMMENT 'Each desk operates with independent VaR and position limits approved by the CRO; gas desk covers pipeline gas and LNG; carbon desk trades EU ETS allowances (EUAs) and Certified Emission Reductions (CERs)',
# MAGIC   valuation_date DATE NOT NULL,
# MAGIC   var_95_eur DECIMAL(15,2) COMMENT 'Maximum expected portfolio loss at 95% confidence over a 1-day holding period under normal market conditions; used for internal management and board reporting',
# MAGIC   var_99_eur DECIMAL(15,2) COMMENT 'Maximum expected portfolio loss at 99% confidence over a 1-day holding period; the regulatory minimum for EMIR capital adequacy and MiFID internal model method; the primary figure used by the CRO for limit monitoring',
# MAGIC   portfolio_value_eur DECIMAL(15,2),
# MAGIC   CONSTRAINT pk_var_reports PRIMARY KEY (report_id)
# MAGIC ) COMMENT 'Daily VaR snapshot per trading desk; 99% confidence level is required for MiFID/EMIR regulatory capital calculations; CRO uses this to monitor each desk against its board-approved VaR limit; consecutive days at >80% of limit trigger an early warning alert';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.risk_management.credit_exposures (
# MAGIC   exposure_id INT NOT NULL,
# MAGIC   counterparty_id INT NOT NULL COMMENT 'FK to counterparties',
# MAGIC   exposure_eur DECIMAL(15,2) COMMENT 'Current replacement cost if the counterparty were to default today (in-the-money positions only); always >= 0 from the company perspective; recalculated daily by the risk system after market close using live forward curves',
# MAGIC   collateral_held_eur DECIMAL(15,2) COMMENT 'Cash or high-quality liquid assets posted by the counterparty under the Credit Support Annex (CSA); directly offsets exposure_eur and reduces regulatory capital requirement',
# MAGIC   net_exposure_eur DECIMAL(15,2) COMMENT 'exposure_eur minus collateral_held_eur; represents actual unhedged credit risk; compared against counterparties.credit_limit_eur to determine available trading headroom for this counterparty',
# MAGIC   calculation_date DATE NOT NULL,
# MAGIC   CONSTRAINT pk_credit_exposures PRIMARY KEY (exposure_id),
# MAGIC   CONSTRAINT fk_exposure_cpty FOREIGN KEY (counterparty_id) REFERENCES dc_demo_energy_trading.positions.counterparties(counterparty_id)
# MAGIC ) COMMENT 'Daily mark-to-market credit exposure snapshot per counterparty; net_exposure_eur compared against counterparties.credit_limit_eur determines remaining headroom for new trades; basis for IFRS 13 fair value credit adjustments (CVA)';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_energy_trading.risk_management.limit_breaches (
# MAGIC   breach_id INT NOT NULL,
# MAGIC   desk STRING NOT NULL,
# MAGIC   trader_name STRING COMMENT 'Trader responsible for the breach',
# MAGIC   trader_email STRING COMMENT 'Email of the trader',
# MAGIC   limit_type STRING NOT NULL COMMENT 'var = portfolio VaR limit exceeded; position = single-commodity net position cap breached; credit = counterparty credit_limit_eur exceeded; volume = daily traded volume circuit breaker triggered (operational risk control)',
# MAGIC   limit_value_eur DECIMAL(15,2),
# MAGIC   actual_value_eur DECIMAL(15,2),
# MAGIC   breach_date DATE NOT NULL,
# MAGIC   resolution_status STRING COMMENT 'open = breach reported, line manager notified, must be resolved within 24 hours; escalated = CRO review triggered and documented; resolved = position reduced below limit or temporary limit increase formally approved by the CRO',
# MAGIC   CONSTRAINT pk_limit_breaches PRIMARY KEY (breach_id)
# MAGIC ) COMMENT 'Mandatory audit trail for EMIR and MiFID regulatory compliance; open breaches block new trading on the affected desk until resolved; patterns of repeated breaches on the same desk trigger a formal risk governance review by the CRO';

# COMMAND ----------

# DBTITLE 1,Catalog 3: retail_customers
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CATALOG: retail_customers
# MAGIC -- Residential and commercial energy supply
# MAGIC -- ============================================================
# MAGIC
# MAGIC CREATE CATALOG IF NOT EXISTS dc_demo_retail_customers;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_retail_customers.customer_management;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_retail_customers.metering;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_retail_customers.billing;
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_retail_customers.customer_management
# MAGIC -- Customer profiles, accounts, contracts, interactions
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.customer_management.customers (
# MAGIC   customer_id INT NOT NULL,
# MAGIC   full_name STRING NOT NULL COMMENT 'Customer full name',
# MAGIC   email STRING COMMENT 'Customer email address',
# MAGIC   phone STRING COMMENT 'Customer phone number',
# MAGIC   date_of_birth DATE COMMENT 'Date of birth',
# MAGIC   national_id STRING COMMENT 'National ID or fiscal code; used for identity verification at onboarding and court proceedings in debt recovery; classified as GDPR Article 9 special category data; access restricted to compliance and legal teams only',
# MAGIC   customer_type STRING NOT NULL COMMENT 'Determines regulatory protections applied (residential = full supply license protections), eligible tariff products, smart meter rollout priority order, and the legal process applicable for debt collection and disconnection',
# MAGIC   signup_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'active = supply ongoing; suspended = supply continues but account frozen pending overdue payment (distinct from physical disconnection); churned = switched supplier or vacated; churned records retained 7 years under regulatory obligation',
# MAGIC   CONSTRAINT pk_customers PRIMARY KEY (customer_id)
# MAGIC ) COMMENT 'Master customer register; residential customers are subject to supply license protections (e.g. Ofgem vulnerable customer rules); GDPR data retention: 7 years post-churn; customer_type determines tariff eligibility, smart meter rollout priority, and the applicable debt recovery legal process';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.customer_management.accounts (
# MAGIC   account_id INT NOT NULL,
# MAGIC   customer_id INT NOT NULL COMMENT 'FK to customers',
# MAGIC   account_number STRING NOT NULL COMMENT 'Unique account reference number',
# MAGIC   iban STRING COMMENT 'Used for BACS (UK) or SEPA (EU) Direct Debit collection; must be validated against the bank before the first debit run; changes require a 10-day advance notification to the customer under the Direct Debit Guarantee',
# MAGIC   supply_address STRING NOT NULL,
# MAGIC   city STRING,
# MAGIC   postcode STRING,
# MAGIC   region STRING COMMENT 'Supply area determining the applicable price cap zone, network tariff (Distribution Use of System charges), and the relevant supply license jurisdiction',
# MAGIC   energy_type STRING NOT NULL COMMENT 'dual_fuel = customer receives both electricity and gas; eligible for combined billing and a bundled tariff discount; drives MPAN vs. MPRN reference and metering team assignment',
# MAGIC   CONSTRAINT pk_accounts PRIMARY KEY (account_id),
# MAGIC   CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES dc_demo_retail_customers.customer_management.customers(customer_id)
# MAGIC ) COMMENT 'Each account maps to one physical supply point; electricity accounts have a unique MPAN, gas accounts have an MPRN; a customer may hold multiple accounts across different addresses or fuel types; account_number is the reference on all bills and regulatory complaints';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.customer_management.contracts (
# MAGIC   contract_id INT NOT NULL,
# MAGIC   account_id INT NOT NULL COMMENT 'FK to accounts',
# MAGIC   tariff_id INT NOT NULL COMMENT 'FK to billing.tariffs',
# MAGIC   start_date DATE NOT NULL,
# MAGIC   end_date DATE,
# MAGIC   annual_consumption_kwh DECIMAL(12,2) COMMENT 'Estimated annual energy use in kWh; divided by 12 to set the monthly Direct Debit amount; used for Ofgem comparative consumption reporting and for recommending the most cost-effective tariff at renewal',
# MAGIC   auto_renewal BOOLEAN COMMENT 'True = contract automatically rolls to the standard variable tariff at expiry if the customer takes no action; must be disclosed at sign-up and communicated in the mandatory 42-49 day renewal notification letter',
# MAGIC   status STRING NOT NULL COMMENT 'active, expired, cancelled',
# MAGIC   CONSTRAINT pk_contracts PRIMARY KEY (contract_id),
# MAGIC   CONSTRAINT fk_contracts_account FOREIGN KEY (account_id) REFERENCES dc_demo_retail_customers.customer_management.accounts(account_id)
# MAGIC ) COMMENT 'Supply contracts governing pricing and terms per account; residential fixed-term contracts must include a renewal notice 42-49 days before end_date; auto_renewal rolls to the standard variable tariff and must be disclosed at sign-up under supply license conditions';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.customer_management.contact_history (
# MAGIC   contact_id BIGINT NOT NULL,
# MAGIC   customer_id INT NOT NULL COMMENT 'FK to customers',
# MAGIC   customer_email STRING COMMENT 'Email address used in this specific interaction; may differ from customers.email if a third party (e.g. carer or family member) is acting on behalf of the account holder; records the actual channel address, not necessarily the master contact',
# MAGIC   channel STRING NOT NULL COMMENT 'call, email, chat, branch, app',
# MAGIC   topic STRING COMMENT 'complaint triggers mandatory 8-week Ofgem resolution clock and formal regulatory logging; billing_query is the most frequent contact reason; tariff_change may trigger a 14-day cooling-off right; meter_reading updates the estimated consumption profile used for billing',
# MAGIC   timestamp TIMESTAMP NOT NULL,
# MAGIC   agent_id INT,
# MAGIC   resolution STRING COMMENT 'resolved, escalated, pending',
# MAGIC   notes STRING COMMENT 'Free-text interaction summary; may contain PII; access controlled to front-line staff and team leads only; GDPR 3-year retention limit; included in Subject Access Request responses',
# MAGIC   CONSTRAINT pk_contact_history PRIMARY KEY (contact_id),
# MAGIC   CONSTRAINT fk_contact_customer FOREIGN KEY (customer_id) REFERENCES dc_demo_retail_customers.customer_management.customers(customer_id)
# MAGIC ) COMMENT 'Full customer contact audit trail; complaints (topic = complaint) trigger an 8-week Ofgem resolution clock; if unresolved, the customer may escalate to the Energy Ombudsman; all contact notes are subject to GDPR Subject Access Requests and retained for 3 years';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_retail_customers.metering
# MAGIC -- Smart meters, readings, events
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.metering.meters (
# MAGIC   meter_id INT NOT NULL,
# MAGIC   account_id INT NOT NULL COMMENT 'FK to customer_management.accounts',
# MAGIC   meter_type STRING NOT NULL COMMENT 'smart = SMETS2 meter with half-hourly remote reads and remote disconnect capability; legacy_digital = quarterly manual reads; legacy_analog = biannual estimated reads; government smart meter programme targets 100% smart coverage',
# MAGIC   serial_number STRING NOT NULL COMMENT 'Manufacturer-assigned serial number printed on the physical meter label; used by field engineers to identify the correct asset on-site and required for SMETS2 commissioning and decommissioning in the DCC national registry',
# MAGIC   manufacturer STRING,
# MAGIC   installation_date DATE,
# MAGIC   energy_type STRING NOT NULL COMMENT 'electricity, gas',
# MAGIC   location_description STRING,
# MAGIC   CONSTRAINT pk_meters PRIMARY KEY (meter_id),
# MAGIC   CONSTRAINT fk_meters_account FOREIGN KEY (account_id) REFERENCES dc_demo_retail_customers.customer_management.accounts(account_id)
# MAGIC ) COMMENT 'Physical metering asset register; smart meters support half-hourly remote reads and remote disconnect/reconnect; each meter maps to exactly one supply account (MPAN or MPRN); serial_number is the physical label used by field engineers for on-site identification';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.metering.consumption_readings (
# MAGIC   reading_id BIGINT NOT NULL,
# MAGIC   meter_id INT NOT NULL COMMENT 'FK to meters',
# MAGIC   timestamp TIMESTAMP NOT NULL,
# MAGIC   consumption_kwh DECIMAL(10,3) COMMENT 'Consumption in kWh (or m3 for gas)',
# MAGIC   reading_type STRING NOT NULL COMMENT 'actual = remote or engineer-verified read (triggers invoice); estimated = system-generated from consumption profile when remote read is unavailable; customer_submitted = unverified manual entry by customer, subject to validation before invoicing',
# MAGIC   CONSTRAINT pk_readings PRIMARY KEY (reading_id),
# MAGIC   CONSTRAINT fk_readings_meter FOREIGN KEY (meter_id) REFERENCES dc_demo_retail_customers.metering.meters(meter_id)
# MAGIC ) COMMENT 'Meter consumption time series; actual reads trigger invoice generation; estimated reads are reconciled against the next actual read; half-hourly smart meter data is submitted to Elexon (electricity settlement) and Xoserve (gas) for BSC/UNC market settlement';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.metering.smart_meter_events (
# MAGIC   event_id BIGINT NOT NULL,
# MAGIC   meter_id INT NOT NULL COMMENT 'FK to meters',
# MAGIC   event_type STRING NOT NULL COMMENT 'tamper_alert = potential meter interference or energy theft, referred to revenue protection team; disconnect = remote supply cut executed (debt or safety); reconnect = supply restored after payment clearance or safety sign-off; communication_loss = meter unreachable, triggers estimated billing fallback',
# MAGIC   timestamp TIMESTAMP NOT NULL,
# MAGIC   details STRING,
# MAGIC   CONSTRAINT pk_meter_events PRIMARY KEY (event_id),
# MAGIC   CONSTRAINT fk_events_meter FOREIGN KEY (meter_id) REFERENCES dc_demo_retail_customers.metering.meters(meter_id)
# MAGIC ) COMMENT 'Operational event log from the meter HAN (Home Area Network) and WAN communications layer; tamper_alerts are forwarded to the revenue protection team within 24 hours; communication_loss events trigger automatic fallback to estimated billing mode within 48 hours';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_retail_customers.billing
# MAGIC -- Invoices, payments, tariffs, debt management
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.billing.tariffs (
# MAGIC   tariff_id INT NOT NULL,
# MAGIC   name STRING NOT NULL COMMENT 'Tariff plan name',
# MAGIC   energy_type STRING NOT NULL COMMENT 'electricity, gas',
# MAGIC   rate_eur_kwh DECIMAL(8,5) COMMENT 'Unit rate charged per kWh consumed; the primary variable component of the customer bill; subject to the Ofgem unit rate cap for residential electricity and gas tariffs',
# MAGIC   standing_charge_eur DECIMAL(8,2) COMMENT 'Fixed daily charge applied regardless of consumption level; covers network costs (DUoS), metering, and supplier fixed costs; subject to the Ofgem standing charge cap for residential tariffs',
# MAGIC   green_energy_pct INT COMMENT 'Percentage of electricity backed by Renewable Energy Guarantee of Origin (REGO) certificates from renewable generators; 100% green tariffs are marketed as zero-carbon supply and are a key customer acquisition differentiator',
# MAGIC   valid_from DATE NOT NULL,
# MAGIC   valid_to DATE COMMENT 'Last date new customers can join this tariff; NULL = currently open for new sign-ups; existing customers on an expired tariff are grandfathered until their contract end_date or auto_renewal triggers migration to the standard variable tariff',
# MAGIC   CONSTRAINT pk_tariffs PRIMARY KEY (tariff_id)
# MAGIC ) COMMENT 'Retail energy tariffs available for customer contracts; new customers cannot join expired tariffs (valid_to < CURRENT_DATE); tariff names and rates are published on the Ofgem/regulator price comparison database and subject to residential unit rate and standing charge caps';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.billing.invoices (
# MAGIC   invoice_id BIGINT NOT NULL,
# MAGIC   account_id INT NOT NULL COMMENT 'FK to customer_management.accounts',
# MAGIC   billing_period_start DATE NOT NULL,
# MAGIC   billing_period_end DATE NOT NULL,
# MAGIC   consumption_kwh DECIMAL(10,3) COMMENT 'Total metered consumption in the billing period; reconciled against actual meter reads; basis for the variable charge component of total_eur using the applicable tariff.rate_eur_kwh',
# MAGIC   total_eur DECIMAL(10,2),
# MAGIC   vat_eur DECIMAL(10,2),
# MAGIC   due_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'issued = sent to customer, awaiting payment by due_date; paid = settled in full; overdue = past due_date with no payment, triggers debt collection workflow; disputed = customer contests the amount, collection suspended pending resolution',
# MAGIC   CONSTRAINT pk_invoices PRIMARY KEY (invoice_id),
# MAGIC   CONSTRAINT fk_invoices_account FOREIGN KEY (account_id) REFERENCES dc_demo_retail_customers.customer_management.accounts(account_id)
# MAGIC ) COMMENT 'Customer invoices generated from meter reads and applied tariff rates; overdue invoices trigger the automated payment reminder sequence leading to debt_cases; disputed invoices are suspended from debt collection until resolved; drives revenue recognition and cash flow reporting';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.billing.payments (
# MAGIC   payment_id BIGINT NOT NULL,
# MAGIC   invoice_id BIGINT NOT NULL COMMENT 'FK to invoices',
# MAGIC   credit_card_number STRING COMMENT 'Full or masked credit card number',
# MAGIC   bank_account_iban STRING COMMENT 'IBAN used for payment',
# MAGIC   amount_eur DECIMAL(10,2) NOT NULL,
# MAGIC   payment_date DATE NOT NULL,
# MAGIC   method STRING NOT NULL COMMENT 'direct_debit = lowest collection cost, auto-collected on due_date; card = immediate clearance but incurs interchange fees; bank_transfer = manual, 1-3 day clearing time; cash = highest fraud risk and requires manual reconciliation by the finance team',
# MAGIC   CONSTRAINT pk_payments PRIMARY KEY (payment_id),
# MAGIC   CONSTRAINT fk_payments_invoice FOREIGN KEY (invoice_id) REFERENCES dc_demo_retail_customers.billing.invoices(invoice_id)
# MAGIC ) COMMENT 'Payments received against invoices; partial payments are permitted (amount_eur may be less than the invoice total); multiple payments per invoice are allowed; used for Direct Debit reconciliation and cash collection reporting to treasury';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_retail_customers.billing.debt_cases (
# MAGIC   case_id INT NOT NULL,
# MAGIC   account_id INT NOT NULL COMMENT 'FK to customer_management.accounts',
# MAGIC   debtor_phone STRING COMMENT 'Phone number for debt collection contact',
# MAGIC   debtor_email STRING COMMENT 'Email for debt collection contact',
# MAGIC   outstanding_eur DECIMAL(10,2),
# MAGIC   days_overdue INT COMMENT 'Number of days since the invoice due_date; drives escalation thresholds and bad debt provisioning calculations; basis for IFRS 9 expected credit loss staging (stage 1/2/3)',
# MAGIC   status STRING NOT NULL COMMENT 'reminder_sent = automated notice sent (~30 days overdue); collection = passed to third-party debt collection agency (~60 days); legal = county court judgment proceedings initiated (~90 days); written_off = balance deemed unrecoverable and removed from accounts receivable',
# MAGIC   last_action_date DATE COMMENT 'Date of the most recent collection action taken; used to ensure regulatory required cooling-off periods between escalation steps are respected; stale cases (no action in 30+ days) are flagged for review',
# MAGIC   CONSTRAINT pk_debt_cases PRIMARY KEY (case_id),
# MAGIC   CONSTRAINT fk_debt_account FOREIGN KEY (account_id) REFERENCES dc_demo_retail_customers.customer_management.accounts(account_id)
# MAGIC ) COMMENT 'Debt cases created when invoices breach the overdue threshold; escalation path: reminder_sent → collection agency → legal proceedings → write-off; regulated residential debt collection procedures apply, including mandatory vulnerability assessment before disconnection';

# COMMAND ----------

# DBTITLE 1,Catalog 4: grid_operations
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CATALOG: grid_operations
# MAGIC -- Distribution network infrastructure and field operations
# MAGIC -- ============================================================
# MAGIC
# MAGIC CREATE CATALOG IF NOT EXISTS dc_demo_grid_operations;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_grid_operations.network_assets;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_grid_operations.field_operations;
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_grid_operations.network_assets
# MAGIC -- Physical network infrastructure registry
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.network_assets.substations (
# MAGIC   substation_id INT NOT NULL,
# MAGIC   name STRING NOT NULL,
# MAGIC   voltage_level_kv DECIMAL(7,1) COMMENT 'Operating voltage: 132kV+ = transmission or primary substation; 33-66kV = primary distribution; 11kV = secondary distribution; voltage level determines inspection frequency, regulatory obligations, and which type of licensed engineers are authorised to work on the asset',
# MAGIC   capacity_mva DECIMAL(10,2) COMMENT 'Maximum demand the substation can serve (MVA = MW ÷ power factor, typically 0.95); used for network headroom calculations and connection offer assessments for new generators or large customers',
# MAGIC   latitude DOUBLE,
# MAGIC   longitude DOUBLE,
# MAGIC   region STRING,
# MAGIC   commissioned_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'operational, under_maintenance, decommissioned',
# MAGIC   CONSTRAINT pk_substations PRIMARY KEY (substation_id)
# MAGIC ) COMMENT 'Primary nodes of the electricity distribution network where voltage is stepped down for delivery to end users; an outage at a substation interrupts supply to all downstream customers; used for network capacity planning and connection offer assessments';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.network_assets.transformers (
# MAGIC   transformer_id INT NOT NULL,
# MAGIC   substation_id INT NOT NULL COMMENT 'FK to substations',
# MAGIC   rating_mva DECIMAL(10,2) COMMENT 'Maximum continuous load the transformer can carry without accelerated winding ageing; sustained overload increases insulation degradation; operate with 20% headroom to maintain N-1 security standard',
# MAGIC   voltage_primary_kv DECIMAL(7,1) COMMENT 'Incoming high-voltage feed from the upstream network; paired with voltage_secondary_kv to define the step-down ratio and determine the authorisation level required for maintenance work',
# MAGIC   voltage_secondary_kv DECIMAL(7,1) COMMENT 'Output voltage fed to the downstream distribution network; together with voltage_primary_kv defines the transformation ratio',
# MAGIC   manufacturer STRING,
# MAGIC   installation_date DATE,
# MAGIC   last_inspection_date DATE,
# MAGIC   oil_condition STRING COMMENT 'Transformer oil acts as both insulator and coolant; good = dissolved gas analysis (DGA) within normal limits; degraded = early-stage breakdown detected, plan replacement within 12 months; critical = immediate failure risk, take out of service within 30 days',
# MAGIC   CONSTRAINT pk_transformers PRIMARY KEY (transformer_id),
# MAGIC   CONSTRAINT fk_transformers_sub FOREIGN KEY (substation_id) REFERENCES dc_demo_grid_operations.network_assets.substations(substation_id)
# MAGIC ) COMMENT 'Highest-value and longest lead-time assets in the distribution network; typical replacement cost £500k-£3M with 12-24 month delivery; oil_condition is the primary health indicator and may override the standard scheduled inspection interval';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.network_assets.distribution_lines (
# MAGIC   line_id INT NOT NULL,
# MAGIC   from_substation_id INT NOT NULL COMMENT 'FK to substations (origin)',
# MAGIC   to_substation_id INT NOT NULL COMMENT 'FK to substations (destination)',
# MAGIC   length_km DECIMAL(8,2),
# MAGIC   voltage_kv DECIMAL(7,1),
# MAGIC   conductor_type STRING COMMENT 'ACSR = Aluminium Conductor Steel Reinforced, the most common overhead type; underground_copper = higher capacity per cross-section, preferred in urban areas; conductor type determines the thermal rating, inspection frequency, and applicable fault repair procedure',
# MAGIC   max_current_a DECIMAL(8,2) COMMENT 'Thermal current rating in amperes; sustained exceedance causes conductor sag (flashover risk near vegetation) and accelerated insulation ageing; network operators must not exceed this under normal N-1 operating conditions',
# MAGIC   status STRING NOT NULL,
# MAGIC   CONSTRAINT pk_distribution_lines PRIMARY KEY (line_id),
# MAGIC   CONSTRAINT fk_lines_from FOREIGN KEY (from_substation_id) REFERENCES dc_demo_grid_operations.network_assets.substations(substation_id),
# MAGIC   CONSTRAINT fk_lines_to FOREIGN KEY (to_substation_id) REFERENCES dc_demo_grid_operations.network_assets.substations(substation_id)
# MAGIC ) COMMENT 'Overhead and underground cables forming the distribution network; overhead lines account for ~80% of weather-related outages and are cheaper to install but exposed to vegetation and weather; underground cables have a lower fault rate but higher excavation repair cost';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.network_assets.grid_connection_points (
# MAGIC   connection_id INT NOT NULL,
# MAGIC   substation_id INT NOT NULL COMMENT 'FK to substations',
# MAGIC   connected_entity_type STRING NOT NULL COMMENT 'generation_plant or renewable_site = generation license obligations apply; industrial_customer = demand connection agreement governs; interconnector = international transmission license required; entity type determines inspection regime and fault response priority',
# MAGIC   connected_entity_id INT COMMENT 'ID of the connected entity in its respective table',
# MAGIC   capacity_mw DECIMAL(10,2),
# MAGIC   connection_date DATE,
# MAGIC   CONSTRAINT pk_grid_connections PRIMARY KEY (connection_id),
# MAGIC   CONSTRAINT fk_connections_sub FOREIGN KEY (substation_id) REFERENCES dc_demo_grid_operations.network_assets.substations(substation_id)
# MAGIC ) COMMENT 'Registry of all connection points linking generators, large industrial customers, and interconnectors to the network; capacity_mw constrains total energy flow at each point; used for power flow modelling, connection offer assessments, and fault isolation planning';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_grid_operations.field_operations
# MAGIC -- Work orders, crews, inspections, outages, vegetation
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.field_operations.work_orders (
# MAGIC   order_id INT NOT NULL,
# MAGIC   asset_id INT NOT NULL COMMENT 'ID of the network asset',
# MAGIC   asset_type STRING NOT NULL COMMENT 'substation, transformer, distribution_line',
# MAGIC   order_type STRING NOT NULL COMMENT 'repair, upgrade, inspection, emergency',
# MAGIC   priority STRING NOT NULL COMMENT 'Regulated response SLAs: critical = 2 hours (active outage or imminent danger); high = 4 hours (elevated safety risk); medium = next business day; low = within 5 business days; critical orders require supervisor sign-off before closure',
# MAGIC   requestor_name STRING COMMENT 'Name of person who raised the order',
# MAGIC   requestor_email STRING COMMENT 'Email of the requestor',
# MAGIC   assigned_crew_id INT COMMENT 'FK to field_crews',
# MAGIC   scheduled_date DATE,
# MAGIC   completion_date DATE,
# MAGIC   status STRING NOT NULL COMMENT 'open, assigned, in_progress, completed, cancelled',
# MAGIC   CONSTRAINT pk_work_orders PRIMARY KEY (order_id)
# MAGIC ) COMMENT 'Field work orders for all network assets; critical orders are linked to live outages and carry regulated response time SLAs; order_type and asset_type together determine which engineering team is dispatched and which safety protocols apply; used for Ofgem fault response time reporting';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.field_operations.field_crews (
# MAGIC   crew_id INT NOT NULL,
# MAGIC   crew_leader_name STRING NOT NULL COMMENT 'Full name of crew leader',
# MAGIC   crew_leader_phone STRING NOT NULL COMMENT 'Phone number of crew leader',
# MAGIC   base_location STRING,
# MAGIC   specialization STRING COMMENT 'Determines which asset types the crew is qualified to work on under statutory safety rules; high_voltage crews hold Authorised Person status for HV switching operations; sending the wrong specialisation to a job is a statutory safety violation',
# MAGIC   team_size INT,
# MAGIC   availability_status STRING NOT NULL COMMENT 'available = crew at base, ready for immediate dispatch; deployed = assigned to an active work order; off_duty = mandatory rest period under Working Time Regulations, crew must not be dispatched even for emergencies without a risk assessment',
# MAGIC   CONSTRAINT pk_field_crews PRIMARY KEY (crew_id)
# MAGIC ) COMMENT 'Field maintenance crew register; crew specialisation must match the asset_type on the assigned work order to comply with statutory safety requirements; crew leader is the legally Authorised Person responsible on-site and must hold authorisation for the relevant voltage level';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.field_operations.inspections (
# MAGIC   inspection_id INT NOT NULL,
# MAGIC   asset_id INT NOT NULL,
# MAGIC   asset_type STRING NOT NULL COMMENT 'substation, transformer, distribution_line',
# MAGIC   inspector_name STRING COMMENT 'Name of the inspector',
# MAGIC   inspector_phone STRING COMMENT 'Phone number of the inspector',
# MAGIC   inspection_date DATE NOT NULL,
# MAGIC   condition_rating STRING NOT NULL COMMENT 'excellent/good = continue standard inspection schedule; fair = increase monitoring frequency; poor = raise remediation work order within 30 days; critical = take asset out of service immediately pending emergency repair or replacement',
# MAGIC   findings STRING,
# MAGIC   next_inspection_due DATE COMMENT 'Next mandatory inspection date; interval set by asset criticality and condition: critical assets inspected annually, good condition assets every 3-5 years; overdue date breaches the network licence asset management condition',
# MAGIC   CONSTRAINT pk_inspections PRIMARY KEY (inspection_id)
# MAGIC ) COMMENT 'Periodic condition assessments of network assets; condition_rating below fair automatically triggers a remediation work order in the asset management system; inspection frequency varies by asset criticality and voltage level; overdue inspections breach the network licence obligation';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.field_operations.outage_tickets (
# MAGIC   ticket_id INT NOT NULL,
# MAGIC   affected_substation_id INT NOT NULL COMMENT 'FK to substations',
# MAGIC   start_time TIMESTAMP NOT NULL,
# MAGIC   restoration_time TIMESTAMP,
# MAGIC   customers_affected INT COMMENT 'Number of customers without supply at peak impact; used to calculate SAIDI and SAIFI reliability indices for Ofgem reporting; events above 1,000 customers trigger mandatory regulator notification within 30 minutes',
# MAGIC   cause STRING COMMENT 'vegetation = tree or branch contact with overhead line (most preventable cause, ~30% of outages); equipment_failure = asset breakdown; third_party_damage = typically vehicle collision with a network pole; cause analysis drives the vegetation management and asset replacement programme',
# MAGIC   weather_related BOOLEAN,
# MAGIC   CONSTRAINT pk_outage_tickets PRIMARY KEY (ticket_id),
# MAGIC   CONSTRAINT fk_outage_substation FOREIGN KEY (affected_substation_id) REFERENCES dc_demo_grid_operations.network_assets.substations(substation_id)
# MAGIC ) COMMENT 'Distribution outage tracker; SAIDI (average interruption duration per customer) and SAIFI (average interruption frequency) reliability indices are calculated from this table and submitted to Ofgem; major events affecting >1,000 customers require regulator notification within 30 minutes';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_grid_operations.field_operations.vegetation_management (
# MAGIC   task_id INT NOT NULL,
# MAGIC   line_id INT NOT NULL COMMENT 'FK to distribution_lines',
# MAGIC   corridor_section STRING COMMENT 'Km marker or section identifier',
# MAGIC   risk_level STRING COMMENT 'Based on vegetation height relative to the statutory electrical clearance distance; high = vegetation within or likely to breach the clearance corridor within 3 months, triggers priority scheduling; medium = expected to breach within 12 months; low = within safe limits, next scheduled cycle',
# MAGIC   scheduled_date DATE,
# MAGIC   completion_date DATE,
# MAGIC   contractor STRING,
# MAGIC   status STRING NOT NULL COMMENT 'planned, in_progress, completed',
# MAGIC   CONSTRAINT pk_vegetation PRIMARY KEY (task_id),
# MAGIC   CONSTRAINT fk_veg_line FOREIGN KEY (line_id) REFERENCES dc_demo_grid_operations.network_assets.distribution_lines(line_id)
# MAGIC ) COMMENT 'Proactive vegetation encroachment management for overhead distribution lines; vegetation contact causes ~30% of all distribution outages; high-risk sections must be cleared before the risk materialises to avoid regulatory penalty for preventable supply interruptions';

# COMMAND ----------

# DBTITLE 1,Catalog 5: corporate
# MAGIC %sql
# MAGIC -- ============================================================
# MAGIC -- CATALOG: corporate
# MAGIC -- Shared services: HR, Finance, Compliance
# MAGIC -- ============================================================
# MAGIC
# MAGIC CREATE CATALOG IF NOT EXISTS dc_demo_corporate;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_corporate.human_resources;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_corporate.finance;
# MAGIC CREATE SCHEMA IF NOT EXISTS dc_demo_corporate.compliance;
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_corporate.human_resources
# MAGIC -- Employees, compensation, departments, training
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.human_resources.departments (
# MAGIC   department_id INT NOT NULL,
# MAGIC   name STRING NOT NULL COMMENT 'Department name',
# MAGIC   cost_center STRING NOT NULL COMMENT 'References dc_demo_corporate.finance.cost_centers.cost_center_id; all department expenditure is posted against this code in the general ledger; used for budget variance analysis and inter-business-unit cost allocation',
# MAGIC   business_unit STRING COMMENT 'generation, trading, retail, grid, corporate',
# MAGIC   head_count INT,
# MAGIC   location STRING,
# MAGIC   CONSTRAINT pk_departments PRIMARY KEY (department_id)
# MAGIC ) COMMENT 'Organisational department register; each department maps to exactly one cost center in dc_demo_corporate.finance.cost_centers; used for headcount reporting, budget allocation, and inter-company cost recharge across business units';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.human_resources.employees (
# MAGIC   employee_id INT NOT NULL,
# MAGIC   full_name STRING NOT NULL COMMENT 'Employee full legal name',
# MAGIC   email STRING NOT NULL COMMENT 'Corporate email address',
# MAGIC   phone STRING COMMENT 'Personal phone number',
# MAGIC   date_of_birth DATE COMMENT 'Date of birth',
# MAGIC   national_id STRING COMMENT 'National ID / social security number',
# MAGIC   department_id INT NOT NULL COMMENT 'FK to departments',
# MAGIC   position STRING NOT NULL,
# MAGIC   level STRING COMMENT 'Seniority band determining compensation range, procurement approval authority (e.g. capex sign-off thresholds), and system access tier; director and above are Persons of Significant Influence (PSI) under FCA rules and must be individually approved by the regulator',
# MAGIC   hire_date DATE NOT NULL,
# MAGIC   termination_date DATE,
# MAGIC   manager_id INT COMMENT 'Self-referencing FK to the employee\'s direct line manager; constructs the approval hierarchy for purchase orders, trade limit overrides, and leave authorisation; NULL for the CEO',
# MAGIC   status STRING NOT NULL COMMENT 'active, on_leave, terminated',
# MAGIC   CONSTRAINT pk_employees PRIMARY KEY (employee_id),
# MAGIC   CONSTRAINT fk_emp_dept FOREIGN KEY (department_id) REFERENCES dc_demo_corporate.human_resources.departments(department_id)
# MAGIC ) COMMENT 'Employee master register; active employees with access to trading systems are subject to FCA/MiFID personal account dealing restrictions; termination triggers a mandatory 24-hour system deprovisioning SLA to prevent unauthorised data access';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.human_resources.compensation (
# MAGIC   comp_id INT NOT NULL,
# MAGIC   employee_id INT NOT NULL COMMENT 'FK to employees',
# MAGIC   bank_account_iban STRING COMMENT 'Account where salary is paid via BACS/SEPA; any change requires dual-authorisation in the HR system to prevent social engineering payroll fraud; all changes are logged as security events reviewed by the payroll security team',
# MAGIC   routing_number STRING COMMENT 'UK sort code or SEPA BIC code used alongside bank_account_iban for salary payment routing; must be validated against the bank directory before the first payment run',
# MAGIC   base_salary_eur DECIMAL(10,2),
# MAGIC   bonus_eur DECIMAL(10,2) COMMENT 'Discretionary annual bonus paid in Q1 of the following year; VP and above are subject to MiFID II variable pay deferral (40-60% deferred over 3 years to align incentives with risk outcomes); NULL if no bonus was awarded',
# MAGIC   currency STRING COMMENT 'Defaults to EUR at insert time',
# MAGIC   effective_date DATE NOT NULL,
# MAGIC   CONSTRAINT pk_compensation PRIMARY KEY (comp_id),
# MAGIC   CONSTRAINT fk_comp_emp FOREIGN KEY (employee_id) REFERENCES dc_demo_corporate.human_resources.employees(employee_id)
# MAGIC ) COMMENT 'Compensation history with one row per package version; LAG() on effective_date required to detect changes; IBAN changes trigger a security alert workflow to prevent social engineering fraud; senior traders are subject to MiFID II variable pay deferral rules (40-60% deferred over 3 years)';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.human_resources.training_records (
# MAGIC   record_id INT NOT NULL,
# MAGIC   employee_id INT NOT NULL COMMENT 'FK to employees',
# MAGIC   employee_email STRING COMMENT 'Employee email for certificate delivery',
# MAGIC   instructor_name STRING COMMENT 'Name of the instructor/trainer',
# MAGIC   course_name STRING NOT NULL,
# MAGIC   certification_type STRING COMMENT 'safety = mandatory for site access (e.g. HV switching authorisation, confined space); technical = role-specific skills; compliance = FCA/MiFID regulatory qualification for trading and advisory staff; leadership = optional management development programme',
# MAGIC   completion_date DATE,
# MAGIC   expiry_date DATE COMMENT 'Renewal deadline for time-limited certifications; safety certs (e.g. HV authorisation) automatically revoke site access 1 day after expiry; compliance certs (e.g. FCA CF30) trigger mandatory regulator notification if they lapse',
# MAGIC   passed BOOLEAN,
# MAGIC   CONSTRAINT pk_training PRIMARY KEY (record_id),
# MAGIC   CONSTRAINT fk_training_emp FOREIGN KEY (employee_id) REFERENCES dc_demo_corporate.human_resources.employees(employee_id)
# MAGIC ) COMMENT 'Training and certification register; mandatory safety certifications block site access if expired; compliance certifications (FCA CF30, MiFID competence assessments) for trading staff are reported to the regulator and must not lapse; used to verify pre-requisites before role changes';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_corporate.finance
# MAGIC -- General ledger, cost centers, capex, vendor payments
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.finance.cost_centers (
# MAGIC   cost_center_id STRING NOT NULL COMMENT 'Cost center code',
# MAGIC   name STRING NOT NULL,
# MAGIC   business_unit STRING COMMENT 'generation, trading, retail, grid, corporate',
# MAGIC   budget_eur DECIMAL(15,2) COMMENT 'Full-year approved expenditure budget set at the start of the fiscal year; mid-year revisions require CFO sign-off; the denominator in budget utilisation and burn-rate calculations reported monthly to the board',
# MAGIC   ytd_actual_eur DECIMAL(15,2) COMMENT 'Cumulative actual spend posted to this cost center in the current fiscal year; refreshed monthly from general_ledger; variance against budget_eur is the primary input to the monthly management reporting pack',
# MAGIC   manager_id INT COMMENT 'FK to human_resources.employees',
# MAGIC   CONSTRAINT pk_cost_centers PRIMARY KEY (cost_center_id)
# MAGIC ) COMMENT 'Budget accountability units aligned to business segments; ytd_actual_eur is refreshed monthly from general_ledger postings; variances >10% against budget_eur trigger CFO review; used for board-level segment reporting under IFRS 8 Operating Segments';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.finance.general_ledger (
# MAGIC   entry_id BIGINT NOT NULL,
# MAGIC   account_code STRING NOT NULL COMMENT 'Chart of accounts code following the IFRS classification; determines whether the posting flows to the P&L (income/expense) or balance sheet (asset/liability); used by finance for financial statement line mapping and segment reporting',
# MAGIC   cost_center_id STRING NOT NULL COMMENT 'FK to cost_centers',
# MAGIC   posting_date DATE NOT NULL,
# MAGIC   amount_eur DECIMAL(15,2),
# MAGIC   currency STRING COMMENT 'Defaults to EUR at insert time',
# MAGIC   description STRING,
# MAGIC   document_ref STRING COMMENT 'Purchase order, invoice number, or journal voucher reference; essential for AP reconciliation and audit trail; auditors use this to trace every posting back to its source document; mandatory on all non-system-generated entries',
# MAGIC   CONSTRAINT pk_general_ledger PRIMARY KEY (entry_id),
# MAGIC   CONSTRAINT fk_gl_cc FOREIGN KEY (cost_center_id) REFERENCES dc_demo_corporate.finance.cost_centers(cost_center_id)
# MAGIC ) COMMENT 'Primary financial accounting record; every financial transaction is posted here; subject to 7-year statutory retention under tax law; feeds monthly management accounts, IFRS statutory reporting, VAT returns, and the EU ETS annual carbon account reconciliation';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.finance.capital_projects (
# MAGIC   project_id INT NOT NULL,
# MAGIC   name STRING NOT NULL,
# MAGIC   business_unit STRING,
# MAGIC   cost_center_id STRING COMMENT 'FK to cost_centers',
# MAGIC   budget_eur DECIMAL(15,2),
# MAGIC   spent_eur DECIMAL(15,2),
# MAGIC   start_date DATE,
# MAGIC   expected_completion DATE,
# MAGIC   status STRING NOT NULL COMMENT 'planning = business case under review, no spend authorised; approved = board or CFO sign-off received, procurement can begin; in_progress = active spend committed; completed = assets capitalised to balance sheet; cancelled = budget released back to cost center',
# MAGIC   CONSTRAINT pk_capital_projects PRIMARY KEY (project_id),
# MAGIC   CONSTRAINT fk_capex_cc FOREIGN KEY (cost_center_id) REFERENCES dc_demo_corporate.finance.cost_centers(cost_center_id)
# MAGIC ) COMMENT 'CAPEX project register; approved status is required before committing any spend; spent_eur tracked via general_ledger postings; used for network licence Regulatory Asset Base (RAB) submissions to the network regulator and IFRS capitalisation threshold reviews';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.finance.vendor_payments (
# MAGIC   payment_id BIGINT NOT NULL,
# MAGIC   vendor_id INT NOT NULL,
# MAGIC   vendor_name STRING NOT NULL,
# MAGIC   vendor_tax_id STRING COMMENT 'EU VAT number or national equivalent; required for VAT reclaim (VIES validation for EU vendors), EC sales list, and anti-fraud checks; must be validated against the official register before the first payment run',
# MAGIC   vendor_iban STRING COMMENT 'Vendor payment IBAN',
# MAGIC   invoice_ref STRING COMMENT 'Vendor-issued invoice reference number; combined with vendor_id forms the duplicate-payment detection key; AP matching validates this against the corresponding purchase order in the procurement system',
# MAGIC   amount_eur DECIMAL(12,2) NOT NULL,
# MAGIC   payment_date DATE NOT NULL,
# MAGIC   cost_center_id STRING COMMENT 'FK to cost_centers',
# MAGIC   CONSTRAINT pk_vendor_payments PRIMARY KEY (payment_id),
# MAGIC   CONSTRAINT fk_vendor_cc FOREIGN KEY (cost_center_id) REFERENCES dc_demo_corporate.finance.cost_centers(cost_center_id)
# MAGIC ) COMMENT 'Outgoing vendor payments; duplicate payment detection relies on the uniqueness of vendor_id + invoice_ref; vendor_tax_id required for VAT reclaim, EC sales list filing, and year-end supplier tax reporting; used for AP reconciliation and cash flow forecasting';
# MAGIC
# MAGIC -- -----------------------------------------------------------
# MAGIC -- Schema: dc_demo_corporate.compliance
# MAGIC -- Safety incidents, regulatory filings, audits
# MAGIC -- -----------------------------------------------------------
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.compliance.safety_incidents (
# MAGIC   incident_id INT NOT NULL,
# MAGIC   location STRING NOT NULL COMMENT 'Site or facility where incident occurred',
# MAGIC   department_id INT COMMENT 'FK to human_resources.departments',
# MAGIC   employee_name STRING COMMENT 'Name of employee involved',
# MAGIC   incident_type STRING NOT NULL COMMENT 'slip_trip_fall, electrical, chemical, vehicle, fire',
# MAGIC   severity STRING NOT NULL COMMENT 'near_miss = no injury, investigate and close out within 7 days; first_aid/medical_treatment = not RIDDOR-reportable; lost_time = RIDDOR-reportable, notify HSE within 15 days; fatality = immediate HSE notification, site may be closed pending investigation',
# MAGIC   incident_date DATE NOT NULL,
# MAGIC   investigation_status STRING NOT NULL COMMENT 'reported, investigating, closed',
# MAGIC   lost_time_days INT COMMENT 'Working days the employee was unable to work; 0 for near_miss, first_aid, and medical_treatment cases; used to calculate LTIFR (Lost Time Injury Frequency Rate) which is a key board-level safety KPI and part of executive remuneration targets',
# MAGIC   root_cause STRING,
# MAGIC   CONSTRAINT pk_safety_incidents PRIMARY KEY (incident_id)
# MAGIC ) COMMENT 'RIDDOR-reportable (UK) and equivalent EU safety incident register; lost_time injuries must be notified to the HSE within 15 days; fatalities require immediate notification; LTIFR (Lost Time Injury Frequency Rate) is reported to the board monthly and to RIDDOR annually';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.compliance.regulatory_filings (
# MAGIC   filing_id INT NOT NULL,
# MAGIC   regulator STRING NOT NULL COMMENT 'OFGEM = UK energy supply and network regulator; EPA = environmental regulator (national equivalent); ENTSO-E = European network of transmission operators (market and grid reporting); each has distinct filing deadlines, formats, and penalty structures',
# MAGIC   filing_type STRING NOT NULL COMMENT 'emissions_declaration = annual EU ETS CO2 surrender return (missed = €100/tonne penalty); price_cap_submission = retail tariff justification to regulator; network_plan = 5-year investment plan for RAB assessment; annual_report = statutory accounts',
# MAGIC   business_unit STRING,
# MAGIC   submission_date DATE,
# MAGIC   period_covered_start DATE,
# MAGIC   period_covered_end DATE,
# MAGIC   status STRING NOT NULL COMMENT 'draft, submitted, accepted, rejected',
# MAGIC   document_url STRING,
# MAGIC   CONSTRAINT pk_regulatory_filings PRIMARY KEY (filing_id)
# MAGIC ) COMMENT 'Regulatory submission tracker across all business units; missed deadlines trigger financial fines; status = rejected requires a corrected resubmission within the regulator-specified timeframe; used for the compliance dashboard reviewed by the CRO and board';
# MAGIC
# MAGIC CREATE OR REPLACE TABLE dc_demo_corporate.compliance.audit_findings (
# MAGIC   finding_id INT NOT NULL,
# MAGIC   audit_id INT NOT NULL COMMENT 'Internal or external audit reference',
# MAGIC   area STRING NOT NULL COMMENT 'Audit domain determines responsible team and escalation path: financial → CFO; operational → COO; safety → HSE manager; environmental → sustainability director; IT → CISO; cross-area findings are co-owned with both owners accountable',
# MAGIC   business_unit STRING,
# MAGIC   severity STRING NOT NULL COMMENT 'observation = best practice gap, no mandatory action; minor = low-risk control deviation, remediate within 90 days; major = significant control failure, remediate within 30 days and report to board audit committee; critical = immediate action and potential regulatory disclosure obligation',
# MAGIC   finding_description STRING NOT NULL,
# MAGIC   remediation_plan STRING,
# MAGIC   due_date DATE COMMENT 'Remediation deadline agreed with auditors; overdue major and critical findings are automatically escalated to the board audit committee at the next quarterly meeting',
# MAGIC   status STRING NOT NULL COMMENT 'open = finding raised, remediation not yet started; in_progress = fix under way; closed = remediation verified by auditors; overdue = past due_date without closure, triggers board escalation',
# MAGIC   CONSTRAINT pk_audit_findings PRIMARY KEY (finding_id)
# MAGIC ) COMMENT 'Internal and external audit finding register; major and critical findings are escalated to the board audit committee; a pattern of unresolved critical findings may trigger a regulatory inquiry or threat to the operating licence';

# COMMAND ----------

# DBTITLE 1,Data Model Coherence Analysis
# MAGIC %md
# MAGIC # Data Model Coherence Analysis
# MAGIC
# MAGIC ## Schema-by-Schema Relationship Review
# MAGIC
# MAGIC ### 1. `dc_demo_generation.assets` (3 tables)
# MAGIC - **power_plants** → parent of → **generation_units** (1:N via plant_id)
# MAGIC - **renewable_sites** is a standalone dimension (different asset class, no FK to power_plants since renewables have distinct attributes)
# MAGIC - ✅ Coherent: Plants contain units; renewables are tracked separately because they lack fuel/boiler semantics
# MAGIC
# MAGIC ### 2. `dc_demo_generation.operations` (4 tables)
# MAGIC - **production_logs** → references → generation_units (unit_id)
# MAGIC - **maintenance_orders** → references → generation_units (unit_id) + contains PII (technician)
# MAGIC - **fuel_inventory** → references → power_plants (plant_id) — fuel is procured at plant level
# MAGIC - **outage_events** → references → generation_units (unit_id)
# MAGIC - ✅ Coherent: All operational data ties back to either plant or unit level. Fuel is plant-level (shared storage), production/maintenance/outages are unit-level.
# MAGIC
# MAGIC ### 3. `dc_demo_generation.environmental` (3 tables)
# MAGIC - **emissions_readings** → references → power_plants (plant_id)
# MAGIC - **permits** → references → power_plants (plant_id)
# MAGIC - **environmental_incidents** → references → power_plants (plant_id) + PII (reporter)
# MAGIC - ✅ Coherent: Environmental compliance is managed at plant level (CEMS monitors are plant-scoped, permits are issued per facility)
# MAGIC
# MAGIC ### 4. `dc_demo_energy_trading.market_data` (3 tables)
# MAGIC - **spot_prices**, **forward_curves**, **weather_forecasts** — all reference data with no FKs between them
# MAGIC - ✅ Coherent: These are independent reference/market feeds consumed by traders. They share temporal dimensions (dates) but are sourced from different providers.
# MAGIC
# MAGIC ### 5. `dc_demo_energy_trading.positions` (3 tables)
# MAGIC - **counterparties** → parent for → **trades** (1:N) and **contracts** (1:N)
# MAGIC - **trades** references counterparty + contains PII (trader_name)
# MAGIC - **contracts** references counterparty + contains PII (signatory)
# MAGIC - ✅ Coherent: Standard trading book structure — counterparty is central entity, trades are executions, contracts are long-term agreements.
# MAGIC
# MAGIC ### 6. `dc_demo_energy_trading.risk_management` (3 tables)
# MAGIC - **var_reports** — standalone daily risk snapshots per desk
# MAGIC - **credit_exposures** → references → counterparties (cross-schema FK)
# MAGIC - **limit_breaches** — event-level, contains PII (trader responsible)
# MAGIC - ✅ Coherent: Risk is computed from positions but stored as independent snapshots. Credit exposure links back to counterparty.
# MAGIC
# MAGIC ### 7. `dc_demo_retail_customers.customer_management` (4 tables)
# MAGIC - **customers** → parent of → **accounts** (1:N) → parent of → **contracts** (1:N)
# MAGIC - **contact_history** → references → customers
# MAGIC - ✅ Coherent: Classic CRM model. One customer has multiple supply points (accounts), each account has a contract linked to a tariff.
# MAGIC
# MAGIC ### 8. `dc_demo_retail_customers.metering` (3 tables)
# MAGIC - **meters** → references → accounts (cross-schema)
# MAGIC - **consumption_readings** → references → meters (1:N time-series)
# MAGIC - **smart_meter_events** → references → meters
# MAGIC - ✅ Coherent: Meters are physical devices installed at an account's supply point. Readings and events are time-series data per meter.
# MAGIC
# MAGIC ### 9. `dc_demo_retail_customers.billing` (4 tables)
# MAGIC - **tariffs** — standalone dimension table
# MAGIC - **invoices** → references → accounts (cross-schema)
# MAGIC - **payments** → references → invoices (1:N partial payments possible)
# MAGIC - **debt_cases** → references → accounts
# MAGIC - ✅ Coherent: Invoices are generated from consumption × tariff. Payments settle invoices. Unpaid invoices create debt cases.
# MAGIC
# MAGIC ### 10. `dc_demo_grid_operations.network_assets` (4 tables)
# MAGIC - **substations** → parent for → **transformers** (1:N) and **distribution_lines** (N:N via from/to)
# MAGIC - **grid_connection_points** → references → substations
# MAGIC - ✅ Coherent: Graph topology model — substations are nodes, distribution lines are edges, transformers are components within nodes.
# MAGIC
# MAGIC ### 11. `dc_demo_grid_operations.field_operations` (5 tables)
# MAGIC - **work_orders** → generic (references any asset type + crew) + PII
# MAGIC - **field_crews** — standalone resource table + PII
# MAGIC - **inspections** → generic (any asset type) + PII
# MAGIC - **outage_tickets** → references → substations
# MAGIC - **vegetation_management** → references → distribution_lines
# MAGIC - ✅ Coherent: Polymorphic references (asset_id + asset_type) are appropriate here since work orders and inspections can target any network asset.
# MAGIC
# MAGIC ### 12. `dc_demo_corporate.human_resources` (4 tables)
# MAGIC - **departments** → parent of → **employees** (1:N)
# MAGIC - **employees** → self-referencing (manager_id) + parent of → **compensation** (1:N history) and **training_records** (1:N)
# MAGIC - ✅ Coherent: Standard HR model with org hierarchy, pay history, and competency tracking.
# MAGIC
# MAGIC ### 13. `dc_demo_corporate.finance` (4 tables)
# MAGIC - **cost_centers** → referenced by → **general_ledger**, **capital_projects**, **vendor_payments**
# MAGIC - ✅ Coherent: Cost center is the financial control dimension that links all spend to organizational responsibility.
# MAGIC
# MAGIC ### 14. `dc_demo_corporate.compliance` (3 tables)
# MAGIC - **safety_incidents** → weak reference to departments
# MAGIC - **regulatory_filings** and **audit_findings** — standalone tracking tables
# MAGIC - ✅ Coherent: Compliance data is event-driven and auditor-facing; loose coupling to operational systems is realistic.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Cross-Catalog Relationships (implicit, not enforced by FK)
# MAGIC | From | To | Join Key |
# MAGIC | --- | --- | --- |
# MAGIC | dc_demo_grid_operations.grid_connection_points | dc_demo_generation.power_plants / renewable_sites | connected_entity_id |
# MAGIC | dc_demo_energy_trading.trades | dc_demo_generation.production_logs | Temporal + volume matching |
# MAGIC | dc_demo_corporate.finance.cost_centers | dc_demo_corporate.human_resources.departments | cost_center |
# MAGIC | dc_demo_retail_customers.billing.tariffs | dc_demo_retail_customers.customer_management.contracts | tariff_id |
# MAGIC
# MAGIC ## Verdict
# MAGIC All 13 schemas have internally coherent data models with proper parent-child relationships, realistic cardinalities, and domain-appropriate PII placement.

# COMMAND ----------

# DBTITLE 1,Setup: Data generation helpers
import random
import string
from datetime import date, datetime, timedelta
from decimal import Decimal

random.seed(42)

# --- Name pools (European energy company context) ---
FIRST_NAMES = ["Marco", "Elena", "Lars", "Sophie", "Hans", "Maria", "Pierre", "Anna", "Klaus", "Ingrid",
               "Carlos", "Lucia", "Jan", "Katarina", "Thomas", "Beatrice", "Fredrik", "Chiara", "Dieter", "Francesca",
               "Antonio", "Helene", "Bjorn", "Giulia", "Stefan", "Marta", "Erik", "Isabel", "Wolfgang", "Petra",
               "Giovanni", "Claudia", "Henrik", "Rosa", "Franz", "Silvia", "Olaf", "Teresa", "Rainer", "Eva",
               "Luca", "Nadia", "Sven", "Valentina", "Markus", "Andrea", "Jochen", "Sabine", "Matteo", "Monika"]

LAST_NAMES = ["Mueller", "Rossi", "Andersson", "Schmidt", "Dubois", "Garcia", "Jensen", "Fischer", "Martin", "Berg",
              "Bianchi", "Larsson", "Weber", "Moreau", "Fernandez", "Nilsson", "Hoffmann", "Bernard", "Lopez", "Eriksson",
              "Romano", "Johansson", "Bauer", "Leroy", "Martinez", "Olsson", "Koch", "Simon", "Sanchez", "Lindberg",
              "Colombo", "Karlsson", "Wagner", "Laurent", "Perez", "Svensson", "Schreiber", "Morel", "Torres", "Lund",
              "Ricci", "Gustafsson", "Braun", "Petit", "Ruiz", "Persson", "Keller", "Roux", "Diaz", "Holm"]

COMPANY_NAMES = ["NordPower AG", "EuroGas Trading GmbH", "SolarWind BV", "Atlantic Energy PLC", "GreenVolt SA",
                 "Alpine Power Corp", "BalticGrid OY", "MediterranElectric SpA", "RhineEnergy AG", "NorthSea Gas Ltd",
                 "VoltaTrading SA", "WindForce AB", "ThermalGen NV", "HydroAlps AG", "CarbonEx Trading",
                 "ElectraConnect BV", "SunPeak Energy", "GasLink Trading", "PowerBridge PLC", "EnergiaNova SpA"]

CITIES = ["Munich", "Milan", "Stockholm", "Hamburg", "Paris", "Madrid", "Copenhagen", "Vienna", "Amsterdam", "Zurich",
          "Frankfurt", "Rome", "Oslo", "Berlin", "Lyon", "Barcelona", "Helsinki", "Brussels", "Prague", "Warsaw"]

COUNTRIES = ["Germany", "Italy", "Sweden", "France", "Spain", "Netherlands", "Austria", "Denmark", "Norway", "Finland"]

REGIONS = ["North", "South", "East", "West", "Central", "Northeast", "Northwest", "Southeast", "Southwest", "Coastal"]

# --- Helper functions ---
def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def rand_email(name=None):
    if name is None:
        name = rand_name()
    parts = name.lower().split()
    domains = ["energycorp.eu", "nordpower.com", "gridops.de", "eurogas.nl", "powergen.it", "voltex.se"]
    return f"{parts[0]}.{parts[1]}@{random.choice(domains)}"

def rand_phone():
    country_codes = ["+49", "+39", "+46", "+33", "+34", "+31", "+43", "+45", "+47"]
    return f"{random.choice(country_codes)} {random.randint(100,999)} {random.randint(1000000,9999999)}"

def rand_iban():
    country_prefixes = ["DE", "IT", "SE", "FR", "ES", "NL", "AT", "DK"]
    prefix = random.choice(country_prefixes)
    digits = ''.join([str(random.randint(0,9)) for _ in range(20)])
    return f"{prefix}{random.randint(10,99)}{digits}"

def rand_national_id():
    # Looks like a European fiscal code / national ID
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    nums = ''.join([str(random.randint(0,9)) for _ in range(8)])
    return f"{letters}{nums}{random.choice(string.ascii_uppercase)}"

def rand_date(start_year=2018, end_year=2025):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def rand_timestamp(start_year=2024, end_year=2025):
    d = rand_date(start_year, end_year)
    return datetime(d.year, d.month, d.day, random.randint(0,23), random.randint(0,59), random.randint(0,59))

def rand_credit_card():
    return f"{''.join([str(random.randint(0,9)) for _ in range(16)])}"

def rand_serial():
    return f"SM-{random.randint(100000,999999)}-{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}"

def rand_tax_id():
    prefixes = ["DE", "IT", "FR", "ES", "NL", "AT", "SE"]
    return f"{random.choice(prefixes)}{''.join([str(random.randint(0,9)) for _ in range(9)])}"

def sql_str(val):
    """Escape a value for SQL string literal."""
    if val is None:
        return "NULL"
    return f"'{str(val).replace(chr(39), chr(39)+chr(39))}'"

def sql_val(val):
    """Format a value for SQL INSERT."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, (date, datetime)):
        return f"'{val}'"
    return sql_str(val)

def build_insert(table_name, columns, rows):
    """Build and execute a multi-row INSERT statement."""
    cols = ", ".join(columns)
    values_list = []
    for row in rows:
        vals = ", ".join([sql_val(v) for v in row])
        values_list.append(f"({vals})")
    # Execute in batches of 50 to avoid oversized statements
    batch_size = 50
    for i in range(0, len(values_list), batch_size):
        batch = values_list[i:i+batch_size]
        sql = f"INSERT INTO {table_name} ({cols}) VALUES\n" + ",\n".join(batch)
        spark.sql(sql)

print("✓ Data generation helpers loaded.")

# COMMAND ----------

# DBTITLE 1,Insert data: generation catalog
# =============================================================
# CATALOG: generation - Power plants, operations, environmental
# =============================================================

# --- dc_demo_generation.assets.power_plants (50 rows) ---
plant_names = ["Nordheim Gas", "Rheinfeld Coal", "Alpbach Hydro", "Westport Nuclear", "Solaris PV",
               "Brenntal Gas", "Ostsee Wind", "Lombardia CCGT", "Provence Solar", "Baltic LNG",
               "Ruhrberg Coal", "Fjordkraft Hydro", "Sevilla Solar", "Rotterdam Gas", "Praha CCGT",
               "Dresden Biomass", "Gotland Wind", "Napoli Gas", "Lyon Cogen", "Stavanger LNG"]
fuel_types_thermal = ["gas", "coal", "nuclear", "oil", "biomass"]
plant_statuses = ["active", "active", "active", "active", "standby", "decommissioned"]

plant_rows = []
for i in range(1, 51):
    name = f"{random.choice(plant_names)} {i}" if i > 20 else plant_names[i-1] if i <= 20 else f"Plant-{i}"
    if i <= 20:
        name = plant_names[i-1]
    else:
        name = f"{random.choice(['North','South','East','West','Central'])} Power Station {i}"
    fuel = random.choice(fuel_types_thermal)
    cap = round(random.uniform(50, 1200), 2)
    city = random.choice(CITIES)
    country = random.choice(COUNTRIES)
    lat = round(random.uniform(44.0, 60.0), 6)
    lon = round(random.uniform(-3.0, 18.0), 6)
    comm = rand_date(2000, 2020)
    decomm = rand_date(2022, 2025) if random.random() < 0.1 else None
    status = "decommissioned" if decomm else random.choice(["active"]*8 + ["standby"])
    plant_rows.append((i, name, fuel, cap, f"{city} Industrial Zone", city, country, lat, lon, comm, decomm, status))

build_insert("dc_demo_generation.assets.power_plants",
    ["plant_id", "name", "fuel_type", "capacity_mw", "location", "city", "country", "latitude", "longitude", "commissioned_date", "decommission_date", "status"],
    plant_rows)

# --- dc_demo_generation.assets.generation_units (50 rows) ---
unit_types = ["gas_turbine", "steam_turbine", "boiler", "combined_cycle", "diesel_engine", "reactor"]
unit_statuses = ["operational", "operational", "operational", "maintenance", "retired"]

unit_rows = []
for i in range(1, 51):
    plant_id = random.randint(1, 50)
    utype = random.choice(unit_types)
    cap = round(random.uniform(20, 600), 2)
    eff = round(random.uniform(30, 62), 2)
    overhaul = rand_date(2020, 2025) if random.random() > 0.3 else None
    status = random.choice(unit_statuses)
    unit_rows.append((i, plant_id, utype, cap, eff, overhaul, status))

build_insert("dc_demo_generation.assets.generation_units",
    ["unit_id", "plant_id", "unit_type", "capacity_mw", "efficiency_pct", "last_overhaul_date", "status"],
    unit_rows)

# --- dc_demo_generation.assets.renewable_sites (50 rows) ---
tech_types = ["wind_onshore", "wind_offshore", "solar_pv", "hydro"]

renewable_rows = []
for i in range(1, 51):
    tech = random.choice(tech_types)
    name = f"{random.choice(['Green','Eco','Nord','Sun','Wind','Aqua'])} {random.choice(['Park','Farm','Field','Valley','Ridge'])} {i}"
    cap = round(random.uniform(10, 500), 2)
    units = random.randint(5, 200) if tech.startswith("wind") or tech == "solar_pv" else random.randint(1, 10)
    lat = round(random.uniform(44.0, 62.0), 6)
    lon = round(random.uniform(-5.0, 20.0), 6)
    grid_point = f"GP-{random.randint(100,999)}"
    comm = rand_date(2010, 2024)
    status = random.choice(["active"]*9 + ["under_construction"])
    renewable_rows.append((i, name, tech, cap, units, lat, lon, grid_point, comm, status))

build_insert("dc_demo_generation.assets.renewable_sites",
    ["site_id", "name", "technology", "capacity_mw", "num_units", "latitude", "longitude", "grid_connection_point", "commissioned_date", "status"],
    renewable_rows)

# --- dc_demo_generation.operations.production_logs (50 rows) ---
prod_rows = []
for i in range(1, 51):
    unit_id = random.randint(1, 50)
    ts = rand_timestamp(2024, 2025)
    output = round(random.uniform(5, 500), 3)
    avail = round(random.uniform(70, 100), 2)
    fuel_cons = round(random.uniform(1, 200), 3)
    prod_rows.append((i, unit_id, ts, output, avail, fuel_cons))

build_insert("dc_demo_generation.operations.production_logs",
    ["log_id", "unit_id", "timestamp", "output_mwh", "availability_pct", "fuel_consumed_tonnes"],
    prod_rows)

# --- dc_demo_generation.operations.maintenance_orders (50 rows) ---
order_types = ["preventive", "corrective", "emergency"]
order_statuses = ["open", "in_progress", "completed", "completed", "completed", "cancelled"]

maint_rows = []
for i in range(1, 51):
    unit_id = random.randint(1, 50)
    otype = random.choice(order_types)
    tech_name = rand_name()
    tech_phone = rand_phone()
    sched = rand_date(2024, 2025)
    comp = sched + timedelta(days=random.randint(1, 30)) if random.random() > 0.2 else None
    cost = round(random.uniform(500, 150000), 2)
    status = "completed" if comp else random.choice(["open", "in_progress"])
    maint_rows.append((i, unit_id, otype, tech_name, tech_phone, sched, comp, cost, status))

build_insert("dc_demo_generation.operations.maintenance_orders",
    ["order_id", "unit_id", "order_type", "technician_name", "technician_phone", "scheduled_date", "completion_date", "cost_eur", "status"],
    maint_rows)

# --- dc_demo_generation.operations.fuel_inventory (50 rows) ---
fuel_types_inv = ["gas", "coal", "oil", "uranium", "biomass"]

fuel_rows = []
for i in range(1, 51):
    plant_id = random.randint(1, 50)
    fuel = random.choice(fuel_types_inv)
    qty = round(random.uniform(100, 50000), 3)
    delivery = rand_date(2024, 2025)
    supplier = random.randint(1, 20)
    unit_cost = round(random.uniform(10, 500), 2)
    fuel_rows.append((i, plant_id, fuel, qty, delivery, supplier, unit_cost))

build_insert("dc_demo_generation.operations.fuel_inventory",
    ["inventory_id", "plant_id", "fuel_type", "quantity_tonnes", "delivery_date", "supplier_id", "unit_cost_eur"],
    fuel_rows)

# --- dc_demo_generation.operations.outage_events (50 rows) ---
outage_causes = ["mechanical_failure", "fuel_supply", "grid_constraint", "weather", "electrical_fault", "human_error"]

outage_rows = []
for i in range(1, 51):
    unit_id = random.randint(1, 50)
    start = rand_timestamp(2024, 2025)
    duration_h = random.randint(1, 720)
    end = start + timedelta(hours=duration_h) if random.random() > 0.1 else None
    cause = random.choice(outage_causes)
    energy_lost = round(random.uniform(10, 5000), 3)
    planned = random.random() < 0.3
    outage_rows.append((i, unit_id, start, end, cause, energy_lost, planned))

build_insert("dc_demo_generation.operations.outage_events",
    ["event_id", "unit_id", "start_time", "end_time", "cause", "energy_lost_mwh", "is_planned"],
    outage_rows)

# --- dc_demo_generation.environmental.emissions_readings (50 rows) ---
pollutants = ["CO2", "NOx", "SO2", "particulates"]

emissions_rows = []
for i in range(1, 51):
    plant_id = random.randint(1, 50)
    pollutant = random.choice(pollutants)
    value = round(random.uniform(0.5, 5000), 4)
    mdate = rand_date(2024, 2025)
    emissions_rows.append((i, plant_id, pollutant, value, mdate))

build_insert("dc_demo_generation.environmental.emissions_readings",
    ["reading_id", "plant_id", "pollutant", "value_tonnes", "measurement_date"],
    emissions_rows)

# --- dc_demo_generation.environmental.permits (50 rows) ---
permit_types = ["emissions", "water_discharge", "waste_disposal"]
permit_statuses = ["active", "active", "active", "expired", "pending_renewal"]

permit_rows = []
for i in range(1, 51):
    plant_id = random.randint(1, 50)
    ptype = random.choice(permit_types)
    authority = random.choice(["OFGEM", "EPA", "BNA", "ARERA", "CNMC", "EI"])
    issue = rand_date(2018, 2023)
    expiry = issue + timedelta(days=random.randint(365, 1825))
    max_tonnes = round(random.uniform(100, 100000), 4)
    status = "expired" if expiry < date(2025, 1, 1) else random.choice(["active", "active", "pending_renewal"])
    permit_rows.append((i, plant_id, ptype, authority, issue, expiry, max_tonnes, status))

build_insert("dc_demo_generation.environmental.permits",
    ["permit_id", "plant_id", "permit_type", "issuing_authority", "issue_date", "expiry_date", "max_allowed_tonnes", "status"],
    permit_rows)

# --- dc_demo_generation.environmental.environmental_incidents (50 rows) ---
incident_types_env = ["spill", "leak", "exceedance", "wildlife_impact"]
severities = ["low", "medium", "high", "critical"]

env_incident_rows = []
for i in range(1, 51):
    plant_id = random.randint(1, 50)
    itype = random.choice(incident_types_env)
    sev = random.choice(severities)
    reporter = rand_name()
    reporter_em = rand_email(reporter)
    reported = rand_date(2023, 2025)
    resolved = reported + timedelta(days=random.randint(1, 60)) if random.random() > 0.2 else None
    desc = f"{itype.replace('_',' ').title()} detected at unit area - severity {sev}"
    env_incident_rows.append((i, plant_id, itype, sev, reporter, reporter_em, reported, resolved, desc))

build_insert("dc_demo_generation.environmental.environmental_incidents",
    ["incident_id", "plant_id", "incident_type", "severity", "reporter_name", "reporter_email", "reported_date", "resolution_date", "description"],
    env_incident_rows)

print("✓ generation catalog: all 10 tables populated (~50 rows each).")

# COMMAND ----------

# DBTITLE 1,Insert data: energy_trading catalog
# =============================================================
# CATALOG: energy_trading - Market data, positions, risk
# =============================================================

# --- dc_demo_energy_trading.market_data.spot_prices (50 rows) ---
markets = ["EPEX", "NBP", "TTF", "ICE", "EEX"]
commodities = ["power", "natural_gas", "carbon", "oil"]

spot_rows = []
for i in range(1, 51):
    market = random.choice(markets)
    commodity = random.choice(commodities)
    price = round(random.uniform(15, 350), 4)
    delivery = rand_date(2024, 2025)
    hour = random.randint(0, 23)
    ts = rand_timestamp(2024, 2025)
    spot_rows.append((i, market, commodity, price, delivery, hour, ts))

build_insert("dc_demo_energy_trading.market_data.spot_prices",
    ["price_id", "market", "commodity", "price_eur_mwh", "delivery_date", "hour_of_day", "timestamp"],
    spot_rows)

# --- dc_demo_energy_trading.market_data.forward_curves (50 rows) ---
periods = ["M+1", "M+2", "M+3", "Q+1", "Q+2", "Cal+1", "Cal+2"]

forward_rows = []
for i in range(1, 51):
    commodity = random.choice(commodities)
    period = random.choice(periods)
    d_start = rand_date(2025, 2026)
    d_end = d_start + timedelta(days=random.choice([30, 90, 365]))
    price = round(random.uniform(20, 300), 4)
    val_date = rand_date(2024, 2025)
    forward_rows.append((i, commodity, period, d_start, d_end, price, val_date))

build_insert("dc_demo_energy_trading.market_data.forward_curves",
    ["curve_id", "commodity", "delivery_period", "delivery_start", "delivery_end", "price_eur_mwh", "valuation_date"],
    forward_rows)

# --- dc_demo_energy_trading.market_data.weather_forecasts (50 rows) ---
weather_regions = ["Northern Europe", "Central Europe", "Southern Europe", "Iberian Peninsula", "Scandinavia",
                   "British Isles", "Alpine Region", "Benelux", "Eastern Europe", "Mediterranean"]

weather_rows = []
for i in range(1, 51):
    region = random.choice(weather_regions)
    forecast_d = rand_date(2024, 2025)
    target_d = forecast_d + timedelta(days=random.randint(1, 7))
    temp = round(random.uniform(-5, 38), 2)
    wind = round(random.uniform(0, 25), 2)
    solar = round(random.uniform(0, 1000), 2)
    precip = round(random.uniform(0, 50), 2)
    weather_rows.append((i, region, forecast_d, target_d, temp, wind, solar, precip))

build_insert("dc_demo_energy_trading.market_data.weather_forecasts",
    ["forecast_id", "region", "forecast_date", "target_date", "temperature_c", "wind_speed_ms", "solar_irradiance_wm2", "precipitation_mm"],
    weather_rows)

# --- dc_demo_energy_trading.positions.counterparties (50 rows) ---
cpty_rows = []
for i in range(1, 51):
    legal = random.choice(COMPANY_NAMES) if i <= 20 else f"{random.choice(['Euro','Nord','Global','Trans','Inter'])}{random.choice(['Power','Gas','Energy','Trade','Volt'])} {random.choice(['AG','GmbH','BV','SA','PLC','SpA'])}"
    short = legal.split()[0][:4].upper()
    tax = rand_tax_id()
    iban = rand_iban()
    country = random.choice(COUNTRIES)
    rating = random.choice(["AAA", "AA+", "AA", "A+", "A", "BBB+", "BBB", "BB+"])
    limit = round(random.uniform(1000000, 500000000), 2)
    active = random.random() > 0.1
    cpty_rows.append((i, legal, short, tax, iban, country, rating, limit, active))

build_insert("dc_demo_energy_trading.positions.counterparties",
    ["counterparty_id", "legal_name", "short_name", "tax_id", "bank_account_iban", "country", "credit_rating", "credit_limit_eur", "is_active"],
    cpty_rows)

# --- dc_demo_energy_trading.positions.trades (50 rows) ---
trade_statuses = ["confirmed", "confirmed", "settled", "settled", "cancelled"]

trade_rows = []
for i in range(1, 51):
    trader = rand_name()
    cpty_id = random.randint(1, 50)
    commodity = random.choice(commodities)
    direction = random.choice(["buy", "sell"])
    volume = round(random.uniform(100, 50000), 3)
    price = round(random.uniform(20, 300), 4)
    trade_d = rand_date(2024, 2025)
    del_start = trade_d + timedelta(days=random.randint(1, 30))
    del_end = del_start + timedelta(days=random.choice([1, 7, 30, 90]))
    status = random.choice(trade_statuses)
    trade_rows.append((i, trader, cpty_id, commodity, direction, volume, price, trade_d, del_start, del_end, status))

build_insert("dc_demo_energy_trading.positions.trades",
    ["trade_id", "trader_name", "counterparty_id", "commodity", "direction", "volume_mwh", "price_eur_mwh", "trade_date", "delivery_start", "delivery_end", "status"],
    trade_rows)

# --- dc_demo_energy_trading.positions.contracts (50 rows) ---
contract_types = ["PPA", "tolling", "swap", "futures", "options"]
contract_statuses = ["active", "active", "active", "expired", "terminated"]

contract_rows = []
for i in range(1, 51):
    cpty_id = random.randint(1, 50)
    ctype = random.choice(contract_types)
    signatory = rand_name()
    sig_email = rand_email(signatory)
    start = rand_date(2020, 2024)
    end = start + timedelta(days=random.randint(365, 3650))
    notional = round(random.uniform(100000, 50000000), 2)
    status = "expired" if end < date(2025, 6, 1) else random.choice(["active", "active", "terminated"])
    contract_rows.append((i, cpty_id, ctype, signatory, sig_email, start, end, notional, status))

build_insert("dc_demo_energy_trading.positions.contracts",
    ["contract_id", "counterparty_id", "contract_type", "signatory_name", "signatory_email", "start_date", "end_date", "notional_value_eur", "status"],
    contract_rows)

# --- dc_demo_energy_trading.risk_management.var_reports (50 rows) ---
desks = ["power", "gas", "carbon", "multi_commodity"]

var_rows = []
for i in range(1, 51):
    desk = random.choice(desks)
    val_date = rand_date(2024, 2025)
    var95 = round(random.uniform(50000, 5000000), 2)
    var99 = round(var95 * random.uniform(1.3, 1.8), 2)
    portfolio = round(random.uniform(10000000, 500000000), 2)
    var_rows.append((i, desk, val_date, var95, var99, portfolio))

build_insert("dc_demo_energy_trading.risk_management.var_reports",
    ["report_id", "desk", "valuation_date", "var_95_eur", "var_99_eur", "portfolio_value_eur"],
    var_rows)

# --- dc_demo_energy_trading.risk_management.credit_exposures (50 rows) ---
exposure_rows = []
for i in range(1, 51):
    cpty_id = random.randint(1, 50)
    exposure = round(random.uniform(100000, 20000000), 2)
    collateral = round(exposure * random.uniform(0.1, 0.6), 2)
    net = round(exposure - collateral, 2)
    calc_date = rand_date(2024, 2025)
    exposure_rows.append((i, cpty_id, exposure, collateral, net, calc_date))

build_insert("dc_demo_energy_trading.risk_management.credit_exposures",
    ["exposure_id", "counterparty_id", "exposure_eur", "collateral_held_eur", "net_exposure_eur", "calculation_date"],
    exposure_rows)

# --- dc_demo_energy_trading.risk_management.limit_breaches (50 rows) ---
limit_types = ["var", "position", "credit", "volume"]
resolution_statuses = ["open", "escalated", "resolved", "resolved", "resolved"]

breach_rows = []
for i in range(1, 51):
    desk = random.choice(desks)
    trader = rand_name()
    trader_em = rand_email(trader)
    ltype = random.choice(limit_types)
    limit_val = round(random.uniform(1000000, 50000000), 2)
    actual_val = round(limit_val * random.uniform(1.01, 1.5), 2)
    breach_d = rand_date(2024, 2025)
    res_status = random.choice(resolution_statuses)
    breach_rows.append((i, desk, trader, trader_em, ltype, limit_val, actual_val, breach_d, res_status))

build_insert("dc_demo_energy_trading.risk_management.limit_breaches",
    ["breach_id", "desk", "trader_name", "trader_email", "limit_type", "limit_value_eur", "actual_value_eur", "breach_date", "resolution_status"],
    breach_rows)

print("✓ energy_trading catalog: all 9 tables populated (~50 rows each).")

# COMMAND ----------

# DBTITLE 1,Insert data: retail_customers catalog
# =============================================================
# CATALOG: retail_customers - CRM, metering, billing
# =============================================================

# --- dc_demo_retail_customers.customer_management.customers (50 rows) ---
cust_types = ["residential", "residential", "residential", "commercial", "industrial"]
cust_statuses = ["active", "active", "active", "active", "suspended", "churned"]

cust_rows = []
for i in range(1, 51):
    name = rand_name()
    email = rand_email(name)
    phone = rand_phone()
    dob = rand_date(1955, 2000)
    nid = rand_national_id()
    ctype = random.choice(cust_types)
    signup = rand_date(2015, 2024)
    status = random.choice(cust_statuses)
    cust_rows.append((i, name, email, phone, dob, nid, ctype, signup, status))

build_insert("dc_demo_retail_customers.customer_management.customers",
    ["customer_id", "full_name", "email", "phone", "date_of_birth", "national_id", "customer_type", "signup_date", "status"],
    cust_rows)

# --- dc_demo_retail_customers.customer_management.accounts (50 rows) ---
energy_types = ["electricity", "gas", "dual_fuel"]

account_rows = []
for i in range(1, 51):
    cust_id = random.randint(1, 50)
    acct_num = f"ACC-{random.randint(100000, 999999)}"
    iban = rand_iban()
    address = f"{random.randint(1,200)} {random.choice(['Hauptstrasse','Via Roma','Rue de la Paix','Calle Mayor','Kungsgatan','Damrak'])} {random.randint(1,50)}"
    city = random.choice(CITIES)
    postcode = f"{random.randint(10000, 99999)}"
    region = random.choice(REGIONS)
    etype = random.choice(energy_types)
    account_rows.append((i, cust_id, acct_num, iban, address, city, postcode, region, etype))

build_insert("dc_demo_retail_customers.customer_management.accounts",
    ["account_id", "customer_id", "account_number", "iban", "supply_address", "city", "postcode", "region", "energy_type"],
    account_rows)

# --- dc_demo_retail_customers.billing.tariffs (50 rows, dimension - load before contracts) ---
tariff_names = ["Green Fix 12", "Flex Variable", "Economy 24", "Business Power", "Solar Plus",
                "Night Saver", "All Day Fix", "Eco Smart", "Premium 36", "Starter Plan"]

tariff_rows = []
for i in range(1, 51):
    name = f"{random.choice(tariff_names)} v{random.randint(1,5)}" if i > 10 else tariff_names[i-1]
    etype = random.choice(["electricity", "gas"])
    rate = round(random.uniform(0.05, 0.35), 5)
    standing = round(random.uniform(0.15, 1.50), 2)
    green_pct = random.randint(0, 100)
    valid_from = rand_date(2020, 2024)
    valid_to = valid_from + timedelta(days=random.choice([365, 730, 1095])) if random.random() > 0.3 else None
    tariff_rows.append((i, name, etype, rate, standing, green_pct, valid_from, valid_to))

build_insert("dc_demo_retail_customers.billing.tariffs",
    ["tariff_id", "name", "energy_type", "rate_eur_kwh", "standing_charge_eur", "green_energy_pct", "valid_from", "valid_to"],
    tariff_rows)

# --- dc_demo_retail_customers.customer_management.contracts (50 rows) ---
contract_st = ["active", "active", "active", "expired", "cancelled"]

retail_contract_rows = []
for i in range(1, 51):
    acct_id = random.randint(1, 50)
    tariff_id = random.randint(1, 50)
    start = rand_date(2021, 2024)
    end = start + timedelta(days=random.choice([365, 730])) if random.random() > 0.2 else None
    annual_kwh = round(random.uniform(1500, 150000), 2)
    auto_renew = random.random() > 0.4
    status = "expired" if end and end < date(2025, 1, 1) else random.choice(["active", "active", "cancelled"])
    retail_contract_rows.append((i, acct_id, tariff_id, start, end, annual_kwh, auto_renew, status))

build_insert("dc_demo_retail_customers.customer_management.contracts",
    ["contract_id", "account_id", "tariff_id", "start_date", "end_date", "annual_consumption_kwh", "auto_renewal", "status"],
    retail_contract_rows)

# --- dc_demo_retail_customers.customer_management.contact_history (50 rows) ---
channels = ["call", "email", "chat", "branch", "app"]
topics = ["billing_query", "complaint", "meter_reading", "tariff_change", "moving_home", "payment_issue"]
resolutions = ["resolved", "resolved", "escalated", "pending"]

contact_rows = []
for i in range(1, 51):
    cust_id = random.randint(1, 50)
    # Use the email we'd have for this customer (generate a fresh one for the log)
    cust_email = rand_email()
    channel = random.choice(channels)
    topic = random.choice(topics)
    ts = rand_timestamp(2024, 2025)
    agent_id = random.randint(100, 200)
    resolution = random.choice(resolutions)
    notes = f"{topic.replace('_',' ').title()} - handled via {channel}"
    contact_rows.append((i, cust_id, cust_email, channel, topic, ts, agent_id, resolution, notes))

build_insert("dc_demo_retail_customers.customer_management.contact_history",
    ["contact_id", "customer_id", "customer_email", "channel", "topic", "timestamp", "agent_id", "resolution", "notes"],
    contact_rows)

# --- dc_demo_retail_customers.metering.meters (50 rows) ---
meter_types = ["smart", "smart", "smart", "legacy_digital", "legacy_analog"]
manufacturers = ["Landis+Gyr", "Itron", "Kamstrup", "Sagemcom", "Honeywell", "Elster"]

meter_rows = []
for i in range(1, 51):
    acct_id = random.randint(1, 50)
    mtype = random.choice(meter_types)
    serial = rand_serial()
    mfr = random.choice(manufacturers)
    install = rand_date(2015, 2024)
    etype = random.choice(["electricity", "gas"])
    loc = random.choice(["Basement", "Utility room", "External wall", "Meter cabinet", "Ground floor"])
    meter_rows.append((i, acct_id, mtype, serial, mfr, install, etype, loc))

build_insert("dc_demo_retail_customers.metering.meters",
    ["meter_id", "account_id", "meter_type", "serial_number", "manufacturer", "installation_date", "energy_type", "location_description"],
    meter_rows)

# --- dc_demo_retail_customers.metering.consumption_readings (50 rows) ---
reading_types = ["actual", "actual", "actual", "estimated", "customer_submitted"]

reading_rows = []
for i in range(1, 51):
    meter_id = random.randint(1, 50)
    ts = rand_timestamp(2024, 2025)
    consumption = round(random.uniform(0.5, 150), 3)
    rtype = random.choice(reading_types)
    reading_rows.append((i, meter_id, ts, consumption, rtype))

build_insert("dc_demo_retail_customers.metering.consumption_readings",
    ["reading_id", "meter_id", "timestamp", "consumption_kwh", "reading_type"],
    reading_rows)

# --- dc_demo_retail_customers.metering.smart_meter_events (50 rows) ---
event_types_meter = ["tamper_alert", "disconnect", "reconnect", "firmware_update", "communication_loss"]

sm_event_rows = []
for i in range(1, 51):
    meter_id = random.randint(1, 50)
    etype = random.choice(event_types_meter)
    ts = rand_timestamp(2024, 2025)
    details = f"{etype.replace('_',' ').title()} event recorded"
    sm_event_rows.append((i, meter_id, etype, ts, details))

build_insert("dc_demo_retail_customers.metering.smart_meter_events",
    ["event_id", "meter_id", "event_type", "timestamp", "details"],
    sm_event_rows)

# --- dc_demo_retail_customers.billing.invoices (50 rows) ---
invoice_statuses = ["issued", "paid", "paid", "paid", "overdue", "disputed"]

invoice_rows = []
for i in range(1, 51):
    acct_id = random.randint(1, 50)
    period_start = rand_date(2024, 2025)
    period_end = period_start + timedelta(days=random.choice([28, 30, 31]))
    consumption = round(random.uniform(100, 5000), 3)
    total = round(random.uniform(30, 2000), 2)
    vat = round(total * 0.21, 2)
    due = period_end + timedelta(days=14)
    status = random.choice(invoice_statuses)
    invoice_rows.append((i, acct_id, period_start, period_end, consumption, total, vat, due, status))

build_insert("dc_demo_retail_customers.billing.invoices",
    ["invoice_id", "account_id", "billing_period_start", "billing_period_end", "consumption_kwh", "total_eur", "vat_eur", "due_date", "status"],
    invoice_rows)

# --- dc_demo_retail_customers.billing.payments (50 rows) ---
payment_methods = ["direct_debit", "card", "bank_transfer", "card", "direct_debit"]

payment_rows = []
for i in range(1, 51):
    invoice_id = random.randint(1, 50)
    cc = rand_credit_card() if random.random() > 0.5 else None
    iban = rand_iban() if cc is None else None
    amount = round(random.uniform(30, 2000), 2)
    pay_date = rand_date(2024, 2025)
    method = "card" if cc else random.choice(["direct_debit", "bank_transfer"])
    payment_rows.append((i, invoice_id, cc, iban, amount, pay_date, method))

build_insert("dc_demo_retail_customers.billing.payments",
    ["payment_id", "invoice_id", "credit_card_number", "bank_account_iban", "amount_eur", "payment_date", "method"],
    payment_rows)

# --- dc_demo_retail_customers.billing.debt_cases (50 rows) ---
debt_statuses = ["reminder_sent", "reminder_sent", "collection", "legal", "written_off"]

debt_rows = []
for i in range(1, 51):
    acct_id = random.randint(1, 50)
    phone = rand_phone()
    email = rand_email()
    outstanding = round(random.uniform(50, 5000), 2)
    days_over = random.randint(15, 365)
    status = random.choice(debt_statuses)
    last_action = rand_date(2024, 2025)
    debt_rows.append((i, acct_id, phone, email, outstanding, days_over, status, last_action))

build_insert("dc_demo_retail_customers.billing.debt_cases",
    ["case_id", "account_id", "debtor_phone", "debtor_email", "outstanding_eur", "days_overdue", "status", "last_action_date"],
    debt_rows)

print("✓ retail_customers catalog: all 11 tables populated (~50 rows each).")

# COMMAND ----------

# DBTITLE 1,Insert data: grid_operations catalog
# =============================================================
# CATALOG: grid_operations - Network assets, field operations
# =============================================================

# --- dc_demo_grid_operations.network_assets.substations (50 rows) ---
substation_statuses = ["operational", "operational", "operational", "operational", "under_maintenance", "decommissioned"]
voltage_levels = [11.0, 33.0, 66.0, 110.0, 132.0, 220.0, 400.0]

sub_rows = []
for i in range(1, 51):
    name = f"{random.choice(CITIES)} {random.choice(['North','South','East','West','Central'])} SS-{i:03d}"
    voltage = random.choice(voltage_levels)
    capacity = round(random.uniform(10, 500), 2)
    lat = round(random.uniform(44.0, 60.0), 6)
    lon = round(random.uniform(-3.0, 18.0), 6)
    region = random.choice(REGIONS)
    comm = rand_date(1980, 2020)
    status = random.choice(substation_statuses)
    sub_rows.append((i, name, voltage, capacity, lat, lon, region, comm, status))

build_insert("dc_demo_grid_operations.network_assets.substations",
    ["substation_id", "name", "voltage_level_kv", "capacity_mva", "latitude", "longitude", "region", "commissioned_date", "status"],
    sub_rows)

# --- dc_demo_grid_operations.network_assets.transformers (50 rows) ---
transformer_mfrs = ["Siemens", "ABB", "Hitachi Energy", "GE Grid", "Schneider Electric", "Hyundai", "Toshiba"]
oil_conditions = ["good", "good", "good", "degraded", "critical"]

transformer_rows = []
for i in range(1, 51):
    sub_id = random.randint(1, 50)
    rating = round(random.uniform(5, 300), 2)
    v_primary = random.choice([110.0, 132.0, 220.0, 400.0])
    v_secondary = random.choice([11.0, 33.0, 66.0])
    mfr = random.choice(transformer_mfrs)
    install = rand_date(1990, 2020)
    inspect = rand_date(2022, 2025)
    oil = random.choice(oil_conditions)
    transformer_rows.append((i, sub_id, rating, v_primary, v_secondary, mfr, install, inspect, oil))

build_insert("dc_demo_grid_operations.network_assets.transformers",
    ["transformer_id", "substation_id", "rating_mva", "voltage_primary_kv", "voltage_secondary_kv", "manufacturer", "installation_date", "last_inspection_date", "oil_condition"],
    transformer_rows)

# --- dc_demo_grid_operations.network_assets.distribution_lines (50 rows) ---
conductor_types = ["overhead_aluminium", "underground_copper", "overhead_ACSR", "underground_XLPE"]

line_rows = []
for i in range(1, 51):
    from_sub = random.randint(1, 50)
    to_sub = random.randint(1, 50)
    while to_sub == from_sub:
        to_sub = random.randint(1, 50)
    length = round(random.uniform(0.5, 80), 2)
    voltage = random.choice([11.0, 33.0, 66.0, 110.0])
    conductor = random.choice(conductor_types)
    max_current = round(random.uniform(100, 2000), 2)
    status = random.choice(["active", "active", "active", "maintenance", "decommissioned"])
    line_rows.append((i, from_sub, to_sub, length, voltage, conductor, max_current, status))

build_insert("dc_demo_grid_operations.network_assets.distribution_lines",
    ["line_id", "from_substation_id", "to_substation_id", "length_km", "voltage_kv", "conductor_type", "max_current_a", "status"],
    line_rows)

# --- dc_demo_grid_operations.network_assets.grid_connection_points (50 rows) ---
entity_types = ["generation_plant", "renewable_site", "industrial_customer", "interconnector"]

gcp_rows = []
for i in range(1, 51):
    sub_id = random.randint(1, 50)
    etype = random.choice(entity_types)
    entity_id = random.randint(1, 50)
    capacity = round(random.uniform(5, 500), 2)
    conn_date = rand_date(2005, 2024)
    gcp_rows.append((i, sub_id, etype, entity_id, capacity, conn_date))

build_insert("dc_demo_grid_operations.network_assets.grid_connection_points",
    ["connection_id", "substation_id", "connected_entity_type", "connected_entity_id", "capacity_mw", "connection_date"],
    gcp_rows)

# --- dc_demo_grid_operations.field_operations.field_crews (50 rows) ---
specializations = ["high_voltage", "low_voltage", "underground", "overhead"]
availability = ["available", "available", "deployed", "off_duty"]

crew_rows = []
for i in range(1, 51):
    leader = rand_name()
    phone = rand_phone()
    base = random.choice(CITIES)
    spec = random.choice(specializations)
    size = random.randint(2, 8)
    avail = random.choice(availability)
    crew_rows.append((i, leader, phone, base, spec, size, avail))

build_insert("dc_demo_grid_operations.field_operations.field_crews",
    ["crew_id", "crew_leader_name", "crew_leader_phone", "base_location", "specialization", "team_size", "availability_status"],
    crew_rows)

# --- dc_demo_grid_operations.field_operations.work_orders (50 rows) ---
wo_types = ["repair", "upgrade", "inspection", "emergency"]
wo_priorities = ["low", "medium", "high", "critical"]
wo_statuses = ["open", "assigned", "in_progress", "completed", "completed", "cancelled"]
asset_types_grid = ["substation", "transformer", "distribution_line"]

wo_rows = []
for i in range(1, 51):
    asset_id = random.randint(1, 50)
    atype = random.choice(asset_types_grid)
    otype = random.choice(wo_types)
    priority = random.choice(wo_priorities)
    req_name = rand_name()
    req_email = rand_email(req_name)
    crew_id = random.randint(1, 50)
    sched = rand_date(2024, 2025)
    comp = sched + timedelta(days=random.randint(1, 30)) if random.random() > 0.3 else None
    status = "completed" if comp else random.choice(["open", "assigned", "in_progress"])
    wo_rows.append((i, asset_id, atype, otype, priority, req_name, req_email, crew_id, sched, comp, status))

build_insert("dc_demo_grid_operations.field_operations.work_orders",
    ["order_id", "asset_id", "asset_type", "order_type", "priority", "requestor_name", "requestor_email", "assigned_crew_id", "scheduled_date", "completion_date", "status"],
    wo_rows)

# --- dc_demo_grid_operations.field_operations.inspections (50 rows) ---
condition_ratings = ["excellent", "good", "good", "fair", "poor", "critical"]

inspection_rows = []
for i in range(1, 51):
    asset_id = random.randint(1, 50)
    atype = random.choice(asset_types_grid)
    inspector = rand_name()
    inspector_ph = rand_phone()
    insp_date = rand_date(2023, 2025)
    rating = random.choice(condition_ratings)
    findings = f"Condition: {rating}. {'Requires attention.' if rating in ('poor','critical') else 'No issues found.'}" if random.random() > 0.3 else None
    next_due = insp_date + timedelta(days=random.choice([180, 365, 730]))
    inspection_rows.append((i, asset_id, atype, inspector, inspector_ph, insp_date, rating, findings, next_due))

build_insert("dc_demo_grid_operations.field_operations.inspections",
    ["inspection_id", "asset_id", "asset_type", "inspector_name", "inspector_phone", "inspection_date", "condition_rating", "findings", "next_inspection_due"],
    inspection_rows)

# --- dc_demo_grid_operations.field_operations.outage_tickets (50 rows) ---
outage_causes_grid = ["equipment_failure", "weather", "vegetation", "third_party_damage", "overload"]

outage_ticket_rows = []
for i in range(1, 51):
    sub_id = random.randint(1, 50)
    start = rand_timestamp(2024, 2025)
    restoration = start + timedelta(hours=random.randint(1, 48)) if random.random() > 0.1 else None
    affected = random.randint(50, 50000)
    cause = random.choice(outage_causes_grid)
    weather = cause == "weather" or random.random() < 0.2
    outage_ticket_rows.append((i, sub_id, start, restoration, affected, cause, weather))

build_insert("dc_demo_grid_operations.field_operations.outage_tickets",
    ["ticket_id", "affected_substation_id", "start_time", "restoration_time", "customers_affected", "cause", "weather_related"],
    outage_ticket_rows)

# --- dc_demo_grid_operations.field_operations.vegetation_management (50 rows) ---
veg_statuses = ["planned", "in_progress", "completed", "completed", "completed"]
contractors = ["GreenCut Services", "ArborTech EU", "ForestGuard GmbH", "TreeLine BV", "NatureClear SA"]

veg_rows = []
for i in range(1, 51):
    line_id = random.randint(1, 50)
    section = f"KM {random.randint(0,50)}-{random.randint(51,100)}"
    risk = random.choice(["low", "medium", "high"])
    sched = rand_date(2024, 2025)
    comp = sched + timedelta(days=random.randint(1, 14)) if random.random() > 0.3 else None
    contractor = random.choice(contractors)
    status = "completed" if comp else random.choice(["planned", "in_progress"])
    veg_rows.append((i, line_id, section, risk, sched, comp, contractor, status))

build_insert("dc_demo_grid_operations.field_operations.vegetation_management",
    ["task_id", "line_id", "corridor_section", "risk_level", "scheduled_date", "completion_date", "contractor", "status"],
    veg_rows)

print("✓ grid_operations catalog: all 9 tables populated (~50 rows each).")

# COMMAND ----------

# DBTITLE 1,Insert data: corporate catalog
# =============================================================
# CATALOG: corporate - HR, Finance, Compliance
# =============================================================

# --- dc_demo_corporate.human_resources.departments (50 rows) ---
dept_names = ["Power Generation", "Renewable Operations", "Energy Trading", "Gas Trading", "Carbon Desk",
              "Retail Sales", "Customer Service", "Metering Operations", "Grid Planning", "Field Operations",
              "Network Engineering", "IT & Digital", "Finance & Accounting", "Treasury", "Legal",
              "Human Resources", "Health & Safety", "Environmental Compliance", "Regulatory Affairs", "Procurement",
              "Corporate Strategy", "Investor Relations", "Internal Audit", "Risk Management", "Communications",
              "Fleet Management", "Facilities", "Data & Analytics", "Cybersecurity", "Innovation Lab",
              "Asset Management", "Plant Engineering", "Transmission Planning", "Distribution Design", "Metering Technology",
              "Billing Operations", "Debt Recovery", "Market Analysis", "Weather Forecasting", "Dispatch Center",
              "Emergency Response", "Training Academy", "Quality Assurance", "Project Management", "Construction",
              "Decommissioning", "Waste Management", "Water Management", "Community Relations", "Executive Office"]
business_units = ["generation", "trading", "retail", "grid", "corporate"]

dept_rows = []
for i in range(1, 51):
    name = dept_names[i-1]
    cc = f"CC-{random.randint(1000,9999)}"
    bu = business_units[min(i-1, len(business_units)-1) // 10] if i <= 50 else "corporate"
    # More realistic BU assignment
    if i <= 10: bu = "generation"
    elif i <= 15: bu = "trading"
    elif i <= 25: bu = "retail"
    elif i <= 35: bu = "grid"
    else: bu = "corporate"
    hc = random.randint(5, 200)
    loc = random.choice(CITIES)
    dept_rows.append((i, name, cc, bu, hc, loc))

build_insert("dc_demo_corporate.human_resources.departments",
    ["department_id", "name", "cost_center", "business_unit", "head_count", "location"],
    dept_rows)

# --- dc_demo_corporate.human_resources.employees (50 rows) ---
positions = ["Analyst", "Engineer", "Senior Engineer", "Manager", "Director", "VP", "Specialist",
             "Technician", "Coordinator", "Lead", "Consultant", "Administrator"]
levels = ["junior", "mid", "senior", "lead", "director", "vp"]
emp_statuses = ["active", "active", "active", "active", "on_leave", "terminated"]

emp_rows = []
for i in range(1, 51):
    name = rand_name()
    email = f"{name.lower().replace(' ', '.')}@energycorp.eu"
    phone = rand_phone()
    dob = rand_date(1960, 1998)
    nid = rand_national_id()
    dept_id = random.randint(1, 50)
    position = random.choice(positions)
    level = random.choice(levels)
    hire = rand_date(2005, 2024)
    term = rand_date(2024, 2025) if random.random() < 0.08 else None
    manager_id = random.randint(1, min(i, 50)) if i > 1 else None
    status = "terminated" if term else random.choice(["active"]*9 + ["on_leave"])
    emp_rows.append((i, name, email, phone, dob, nid, dept_id, position, level, hire, term, manager_id, status))

build_insert("dc_demo_corporate.human_resources.employees",
    ["employee_id", "full_name", "email", "phone", "date_of_birth", "national_id", "department_id", "position", "level", "hire_date", "termination_date", "manager_id", "status"],
    emp_rows)

# --- dc_demo_corporate.human_resources.compensation (50 rows) ---
comp_rows = []
for i in range(1, 51):
    emp_id = random.randint(1, 50)
    iban = rand_iban()
    routing = f"{random.randint(10000000, 99999999)}"
    salary = round(random.uniform(35000, 180000), 2)
    bonus = round(salary * random.uniform(0, 0.3), 2)
    currency = "EUR"
    eff_date = rand_date(2022, 2025)
    comp_rows.append((i, emp_id, iban, routing, salary, bonus, currency, eff_date))

build_insert("dc_demo_corporate.human_resources.compensation",
    ["comp_id", "employee_id", "bank_account_iban", "routing_number", "base_salary_eur", "bonus_eur", "currency", "effective_date"],
    comp_rows)

# --- dc_demo_corporate.human_resources.training_records (50 rows) ---
courses = ["High Voltage Safety", "Fire Safety Awareness", "First Aid at Work", "Working at Heights",
           "SCADA Systems", "Gas Safety Certification", "Environmental Awareness", "Leadership Essentials",
           "Data Protection (GDPR)", "Anti-Bribery & Corruption", "Electrical Safety", "Confined Spaces",
           "Risk Assessment", "Project Management Fundamentals", "Cybersecurity Basics"]
cert_types = ["safety", "technical", "compliance", "leadership"]

training_rows = []
for i in range(1, 51):
    emp_id = random.randint(1, 50)
    emp_email = rand_email()
    instructor = rand_name()
    course = random.choice(courses)
    ctype = random.choice(cert_types)
    completion = rand_date(2022, 2025)
    expiry = completion + timedelta(days=random.choice([365, 730, 1095])) if random.random() > 0.3 else None
    passed = random.random() > 0.05
    training_rows.append((i, emp_id, emp_email, instructor, course, ctype, completion, expiry, passed))

build_insert("dc_demo_corporate.human_resources.training_records",
    ["record_id", "employee_id", "employee_email", "instructor_name", "course_name", "certification_type", "completion_date", "expiry_date", "passed"],
    training_rows)

# --- dc_demo_corporate.finance.cost_centers (50 rows) ---
cc_rows = []
for i in range(1, 51):
    cc_id = f"CC-{1000+i}"
    name = f"{random.choice(['Operations','Capital','Maintenance','Admin','Project'])} - {random.choice(CITIES)}"
    bu = random.choice(business_units)
    budget = round(random.uniform(100000, 50000000), 2)
    ytd = round(budget * random.uniform(0.2, 0.95), 2)
    manager = random.randint(1, 50)
    cc_rows.append((cc_id, name, bu, budget, ytd, manager))

build_insert("dc_demo_corporate.finance.cost_centers",
    ["cost_center_id", "name", "business_unit", "budget_eur", "ytd_actual_eur", "manager_id"],
    cc_rows)

# --- dc_demo_corporate.finance.general_ledger (50 rows) ---
account_codes = ["4100", "4200", "5100", "5200", "6100", "6200", "7100", "7200", "8100", "8200"]

gl_rows = []
for i in range(1, 51):
    acct_code = random.choice(account_codes)
    cc_id = f"CC-{random.randint(1001, 1050)}"
    posting = rand_date(2024, 2025)
    amount = round(random.uniform(-500000, 2000000), 2)
    currency = "EUR"
    desc = random.choice(["Monthly depreciation", "Fuel purchase", "Salary allocation", "Maintenance charge",
                          "Revenue recognition", "Tax provision", "Capex accrual", "Insurance premium",
                          "Consulting fees", "Software license"])
    doc_ref = f"DOC-{random.randint(100000, 999999)}"
    gl_rows.append((i, acct_code, cc_id, posting, amount, currency, desc, doc_ref))

build_insert("dc_demo_corporate.finance.general_ledger",
    ["entry_id", "account_code", "cost_center_id", "posting_date", "amount_eur", "currency", "description", "document_ref"],
    gl_rows)

# --- dc_demo_corporate.finance.capital_projects (50 rows) ---
project_names = ["Wind Farm Expansion Phase 2", "Smart Meter Rollout", "Grid Digitalization",
                 "Gas Plant Retrofit", "Solar Park Construction", "Substation Upgrade Programme",
                 "EV Charging Infrastructure", "Battery Storage Pilot", "Offshore Cable Route",
                 "SCADA Modernization", "Nuclear Safety Upgrade", "Data Center Build",
                 "Customer Portal Redesign", "Fleet Electrification", "Hydrogen Pilot Plant"]
capex_statuses = ["planning", "approved", "in_progress", "in_progress", "completed", "cancelled"]

capex_rows = []
for i in range(1, 51):
    name = f"{random.choice(project_names)} - {random.choice(CITIES)}" if i > 15 else project_names[i-1]
    bu = random.choice(business_units)
    cc_id = f"CC-{random.randint(1001, 1050)}"
    budget = round(random.uniform(500000, 100000000), 2)
    spent = round(budget * random.uniform(0, 0.9), 2)
    start = rand_date(2021, 2024)
    expected = start + timedelta(days=random.randint(180, 1460))
    status = random.choice(capex_statuses)
    capex_rows.append((i, name, bu, cc_id, budget, spent, start, expected, status))

build_insert("dc_demo_corporate.finance.capital_projects",
    ["project_id", "name", "business_unit", "cost_center_id", "budget_eur", "spent_eur", "start_date", "expected_completion", "status"],
    capex_rows)

# --- dc_demo_corporate.finance.vendor_payments (50 rows) ---
vendor_names = ["Siemens Energy", "ABB Power", "GE Renewable", "Schneider Electric", "Vestas Wind Systems",
                "Shell Energy", "TotalEnergies Supply", "BP Gas Trading", "Eni SpA", "Equinor ASA",
                "SAP SE", "Accenture", "McKinsey & Co", "Deloitte", "PwC",
                "Kaeser Compressors", "Caterpillar Power", "Rolls-Royce Power", "MAN Energy", "Wartsila"]

vendor_rows = []
for i in range(1, 51):
    vendor_id = random.randint(1, 50)
    v_name = random.choice(vendor_names)
    v_tax = rand_tax_id()
    v_iban = rand_iban()
    invoice_ref = f"INV-{random.randint(100000, 999999)}"
    amount = round(random.uniform(1000, 5000000), 2)
    pay_date = rand_date(2024, 2025)
    cc_id = f"CC-{random.randint(1001, 1050)}"
    vendor_rows.append((i, vendor_id, v_name, v_tax, v_iban, invoice_ref, amount, pay_date, cc_id))

build_insert("dc_demo_corporate.finance.vendor_payments",
    ["payment_id", "vendor_id", "vendor_name", "vendor_tax_id", "vendor_iban", "invoice_ref", "amount_eur", "payment_date", "cost_center_id"],
    vendor_rows)

# --- dc_demo_corporate.compliance.safety_incidents (50 rows) ---
safety_types = ["slip_trip_fall", "electrical", "chemical", "vehicle", "fire"]
safety_severities = ["near_miss", "near_miss", "first_aid", "medical_treatment", "lost_time", "fatality"]
investigation_statuses = ["reported", "investigating", "closed", "closed", "closed"]

safety_rows = []
for i in range(1, 51):
    location = f"{random.choice(CITIES)} - {random.choice(['Power Plant','Substation','Office','Workshop','Field Site'])}"
    dept_id = random.randint(1, 50)
    emp_name = rand_name()
    itype = random.choice(safety_types)
    sev = random.choice(safety_severities)
    inc_date = rand_date(2023, 2025)
    inv_status = random.choice(investigation_statuses)
    lost_days = random.randint(0, 90) if sev in ("lost_time", "fatality") else 0
    root_cause = random.choice(["Inadequate PPE", "Procedure not followed", "Equipment defect", "Environmental conditions", "Training gap", None])
    safety_rows.append((i, location, dept_id, emp_name, itype, sev, inc_date, inv_status, lost_days, root_cause))

build_insert("dc_demo_corporate.compliance.safety_incidents",
    ["incident_id", "location", "department_id", "employee_name", "incident_type", "severity", "incident_date", "investigation_status", "lost_time_days", "root_cause"],
    safety_rows)

# --- dc_demo_corporate.compliance.regulatory_filings (50 rows) ---
regulators = ["OFGEM", "BNA", "ARERA", "CNMC", "EI", "ENTSO-E", "EPA"]
filing_types = ["annual_report", "emissions_declaration", "price_cap_submission", "network_plan", "safety_report"]
filing_statuses = ["draft", "submitted", "accepted", "accepted", "rejected"]

filing_rows = []
for i in range(1, 51):
    regulator = random.choice(regulators)
    ftype = random.choice(filing_types)
    bu = random.choice(business_units)
    submission = rand_date(2023, 2025)
    period_start = date(submission.year - 1, 1, 1)
    period_end = date(submission.year - 1, 12, 31)
    status = random.choice(filing_statuses)
    doc_url = f"https://docs.energycorp.eu/filings/{regulator.lower()}/{ftype}/{submission.year}/{i}"
    filing_rows.append((i, regulator, ftype, bu, submission, period_start, period_end, status, doc_url))

build_insert("dc_demo_corporate.compliance.regulatory_filings",
    ["filing_id", "regulator", "filing_type", "business_unit", "submission_date", "period_covered_start", "period_covered_end", "status", "document_url"],
    filing_rows)

# --- dc_demo_corporate.compliance.audit_findings (50 rows) ---
audit_areas = ["financial", "operational", "safety", "environmental", "IT"]
audit_severities = ["observation", "minor", "minor", "major", "critical"]
audit_statuses = ["open", "in_progress", "closed", "closed", "overdue"]

audit_rows = []
for i in range(1, 51):
    audit_id = random.randint(1, 20)
    area = random.choice(audit_areas)
    bu = random.choice(business_units)
    sev = random.choice(audit_severities)
    desc = random.choice([
        "Incomplete documentation for change management process",
        "Access controls not aligned with least privilege principle",
        "Safety inspection records not digitized within 48 hours",
        "Environmental monitoring gap during equipment changeover",
        "Vendor risk assessment not updated for 12+ months",
        "Backup restoration test not performed in current quarter",
        "Training records missing for two field technicians",
        "Financial reconciliation delayed beyond SLA",
        "Incident report not escalated per procedure",
        "Data retention policy not enforced on legacy systems"
    ])
    remediation = f"Action plan: address {area} finding by due date"
    due = rand_date(2024, 2026)
    status = random.choice(audit_statuses)
    audit_rows.append((i, audit_id, area, bu, sev, desc, remediation, due, status))

build_insert("dc_demo_corporate.compliance.audit_findings",
    ["finding_id", "audit_id", "area", "business_unit", "severity", "finding_description", "remediation_plan", "due_date", "status"],
    audit_rows)

print("✓ corporate catalog: all 11 tables populated (~50 rows each).")

# COMMAND ----------

# DBTITLE 1,Enable Data Classification on All Catalogs
# MAGIC %pip install --upgrade databricks-sdk --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Enable Data Classification on All Catalogs
from databricks.sdk import WorkspaceClient

if dbutils.widgets.get("enable_dc") == "true":
    w = WorkspaceClient()

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if w.config.workspace_id:
        headers["X-Databricks-Workspace-Id"] = w.config.workspace_id

    # Read the usage/budget policy Databricks already resolved for this job's
    # run_as identity (inferred from their accessible policies when the job was
    # created/modified) instead of querying system.billing.usage, which needs
    # metastore-admin SELECT on the system catalog that the job identity may not have.
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    job_id = ctx.tags().get("jobId").getOrElse("")
    if not job_id:
        raise RuntimeError("This cell must run as part of a Databricks Job to resolve a usage policy; no job ID found in the notebook context.")

    job = w.jobs.get(int(job_id))
    usage_policy_id = job.effective_usage_policy_id or job.effective_budget_policy_id
    if not usage_policy_id:
        raise RuntimeError(f"Job {job_id}'s run_as identity has no budget/usage policy assigned; cannot enable data classification.")
    print(f"Using budget policy ID: {usage_policy_id} (resolved from job {job_id})")

    catalogs = ["dc_demo_generation", "dc_demo_energy_trading", "dc_demo_retail_customers", "dc_demo_grid_operations", "dc_demo_corporate"]

    failures = {}
    for catalog_name in catalogs:
        body = {"usage_policy_id": usage_policy_id}
        try:
            w.api_client.do(
                "POST",
                f"/api/data-classification/v1/catalogs/{catalog_name}/config",
                body=body,
                headers=headers
            )
            print(f"Data classification enabled for catalog: {catalog_name}")
        except Exception as e:
            if "ALREADY_EXISTS" in str(e):
                print(f"Data classification already enabled for catalog: {catalog_name}")
            else:
                print(f"Error enabling data classification for {catalog_name}: {e}")
                failures[catalog_name] = e

    if failures:
        raise RuntimeError(f"Failed to enable data classification for: {list(failures.keys())}") from next(iter(failures.values()))
else:
    print("Skipping Data Classification enablement (enable_dc != \"true\")")
