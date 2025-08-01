# MiLB Manager Troubleshooting Guide

## **Issue Summary**
The MiLB manager is no longer pulling accurate game information due to several factors, primarily the current offseason period.

## **Root Causes**

### 1. **Primary Issue: MiLB Offseason**
- **Problem**: MiLB season runs from **April to September**
- **Current Status**: We're in January 2025 (offseason)
- **Impact**: No regular season games are scheduled during offseason
- **Solution**: Enable test mode for offseason testing

### 2. **Secondary Issues**
- **API Endpoint Changes**: MLB Stats API endpoints may have changed
- **Sport ID Updates**: Some sport IDs might be outdated
- **Team Mapping**: Team abbreviations may have changed

## **Solutions Implemented**

### **Immediate Fix: Enable Test Mode**
```json
{
    "milb": {
        "test_mode": true
    }
}
```

### **Code Improvements**
1. **Season Awareness**: Added offseason detection
2. **Better Logging**: More informative error messages
3. **Test Mode Enhancement**: Improved test data

## **Diagnostic Tools Created**

### 1. **Basic API Test**
```bash
python test/test_milb_api.py
```

### 2. **Comprehensive Diagnostic**
```bash
python test/diagnose_milb_issues.py
```

## **Testing the Fixes**

### **Step 1: Run Diagnostic**
```bash
cd /path/to/LEDMatrix
python test/diagnose_milb_issues.py
```

### **Step 2: Test with Test Mode**
1. Ensure `test_mode: true` in config
2. Restart the display system
3. Check if test games appear

### **Step 3: Verify API (When Season Returns)**
```bash
python test/test_milb_api.py
```

## **Expected Behavior**

### **During Offseason (October-March)**
- No real games found
- Test mode shows sample games
- Logs indicate offseason status

### **During Season (April-September)**
- Real games should be found
- Live games display correctly
- Upcoming games show properly

## **Configuration Options**

### **Test Mode**
```json
{
    "milb": {
        "test_mode": true,
        "enabled": true
    }
}
```

### **Season Override (For Testing)**
```json
{
    "milb": {
        "test_mode": true,
        "force_season": true
    }
}
```

## **Common Issues and Solutions**

### **Issue: No Games Found**
- **Cause**: Offseason or API issues
- **Solution**: Enable test mode

### **Issue: API Errors**
- **Cause**: Network or endpoint issues
- **Solution**: Check internet connection and API status

### **Issue: Wrong Team Names**
- **Cause**: Team mapping outdated
- **Solution**: Update `milb_team_mapping.json`

### **Issue: Wrong Sport IDs**
- **Cause**: MLB API changes
- **Solution**: Update sport IDs in config

## **Monitoring and Logs**

### **Key Log Messages**
- `"MiLB is currently in offseason"` - Normal during offseason
- `"Using test mode data for MiLB"` - Test mode active
- `"No games returned from API"` - API issue or offseason

### **Debug Mode**
Enable debug logging to see detailed API calls:
```python
logger.setLevel(logging.DEBUG)
```

## **Future Improvements**

### **Planned Enhancements**
1. **Season Schedule Integration**: Use official season dates
2. **API Fallback**: Multiple API endpoints
3. **Caching Improvements**: Better cache management
4. **Error Recovery**: Automatic retry mechanisms

### **Configuration Enhancements**
```json
{
    "milb": {
        "season_start_month": 4,
        "season_end_month": 9,
        "api_fallback": true,
        "cache_duration": 3600
    }
}
```

## **Contact and Support**

For additional issues:
1. Run the diagnostic tools
2. Check the logs for specific errors
3. Verify network connectivity
4. Test API endpoints directly

## **Quick Reference**

### **Enable Test Mode**
```bash
# Edit config/config.json
# Change "test_mode": false to "test_mode": true
```

### **Run Diagnostics**
```bash
python test/diagnose_milb_issues.py
```

### **Test API Directly**
```bash
python test/test_milb_api.py
```

### **Check Season Status**
- **April-September**: Season active
- **October-March**: Offseason (use test mode) 