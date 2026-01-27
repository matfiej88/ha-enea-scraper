# Enea Energy Meter - Home Assistant Integration

A custom Home Assistant integration for monitoring energy consumption and return from Enea smart meters.

## 📋 Description

This integration allows automatic data retrieval from Enea e-BOK and importing it into Home Assistant as energy statistics. The integration creates two sensors:
- **Enea Energy Consumed** - energy drawn from the grid
- **Enea Energy Returned** - energy returned to the grid (for photovoltaic installations)

Data is automatically synchronized and displayed in the Home Assistant Energy Dashboard.

## ✨ Features

- 🔄 Automatic data synchronization from Enea e-BOK
- 📊 Historical data import
- ⚡ Energy sensors compatible with Energy Dashboard
- 📈 Hourly data with aggregation to statistics
- 🔁 Force refresh capability
- 🗓️ Import data from specific historical date
- 💾 Statistics storage in Home Assistant database

## 📦 Requirements

- Home Assistant 2023.1 or newer
- Active Enea e-BOK account (https://ebok.enea.pl)

## 🚀 Installation

### Method 1: Manual Installation

1. Copy the `custom_components/enea` folder to the `custom_components` directory in your Home Assistant configuration:
   ```
   <config_directory>/custom_components/enea/
   ```

2. The directory structure should look like this:
   ```
   custom_components/
   └── enea/
       ├── __init__.py
       ├── api.py
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── entity_utils.py
       ├── manifest.json
       ├── sensor.py
       └── utils.py
   ```

3. Restart Home Assistant

### Method 2: HACS (if available as repository)

1. Open HACS in Home Assistant
2. Select "Integrations"
3. Click the menu (⋮) and select "Custom repositories"
4. Add the URL of this repository
5. Install the "Enea Energy Meter" integration
6. Restart Home Assistant

## ⚙️ Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ ADD INTEGRATION**
3. Search for **"Enea Scraper"**
4. Fill out the configuration form:
   - **Username**: Your Enea e-BOK login
   - **Password**: Your Enea e-BOK password
   - **Scan Interval**: Data fetch interval in days (default: 1)

**Note**: The Point of Delivery ID (PPE) is now automatically fetched from your Enea account during setup - no manual input required!

### Credential Validation

During setup, the integration will:
1. Validate your credentials by logging into Enea e-BOK
2. Automatically fetch your Point of Delivery ID
3. Create the integration if successful

If you have multiple meters, the integration will use the first one found.

## 🎯 Usage

### Basic Usage

After adding the integration, two new sensors will appear in Home Assistant:
- `sensor.enea_energy_consumed` - total energy consumed
- `sensor.enea_energy_returned` - total energy returned

### Energy Dashboard

The sensors automatically integrate with the Energy Dashboard:

1. Go to **Energy Dashboard**
2. Click **Configure Energy Dashboard**
3. In the **Grid consumption** section:
   - Add `sensor.enea_energy_consumed`
4. In the **Return to grid** section:
   - Add `sensor.enea_energy_returned`

### Available Actions

The integration offers several additional actions available through integration options:

1. Go to **Settings** → **Devices & Services**
2. Find the **Enea Scraper** integration
3. Click **OPTIONS**

Available actions:
- **Force Update** - Immediate data refresh
- **Force Full Reimport** - Clear all statistics and reimport from scratch
- **Import Historical Data** - Import data from a specific historical date

### Importing Historical Data

To import historical data:

1. Open the integration **Options**
2. Select **Import Historical Data**
3. Enter the start date in `YYYY-MM-DD` format (e.g., `2024-01-01`)
4. Confirm - the integration will fetch all data from the specified date to today

## 🔧 Troubleshooting

### Integration Not Fetching Data

1. Verify your Enea e-BOK login and password are correct
2. Check the Point of Delivery ID
3. Check Home Assistant logs: **Settings** → **System** → **Logs**
4. Look for entries containing `enea` or login errors

### No Data on Energy Dashboard Charts

1. Verify sensors are correctly added to Energy Dashboard
2. Wait for full data synchronization (may take a few minutes)
3. Check the date range in Energy Dashboard
4. Try running **Force Update** through integration options

### e-BOK Login Errors

1. Ensure you can log in manually at https://ebok.enea.pl
2. Check if Enea changed your password or requires a password change
3. Verify your account is not locked

### Missing Data for Some Days

This is normal - Enea provides data with some delay (usually 1-2 days). The integration will automatically fetch missing data during the next synchronization.

## 📊 Data Structure

The integration imports hourly data as cumulative statistics. Each reading contains:
- **start**: Timestamp of the measurement start
- **state**: Consumption/return value for that hour (kWh)
- **sum**: Cumulative sum from the beginning (kWh)

## 🔒 Security

- Login credentials are stored in the secure Home Assistant storage
- Connection to Enea e-BOK uses HTTPS
- Password is encrypted and not visible in configuration files

## 🐛 Reporting Issues

If you encounter problems:
1. Enable debug mode for the integration in `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.enea: debug
   ```
2. Restart Home Assistant
3. Perform the action that causes the error
4. Collect logs from **Settings** → **System** → **Logs**
5. Report the issue with logs (remember to remove sensitive data!)

## 📝 License

This project is provided "as is" without any warranties. Use at your own risk.

## 🤝 Contributing

Suggestions and Pull Requests are welcome! 

## 👤 Author

Created for the Home Assistant community in Poland 🇵🇱

## 📚 Additional Information

### Dependencies

The integration requires the following Python libraries (installed automatically):
- `aiohttp` - asynchronous HTTP connections
- `beautifulsoup4` - HTML parsing

### Updates

The integration checks for data once daily (by default). You can change this interval during configuration or force an update through integration options.

### Compatibility

Tested with:
- Home Assistant Core 2023.x - 2026.x
- Enea e-BOK (as of January 2026)

---

**Note**: This integration is not officially supported by Enea. It is a custom solution created by the community.
