# 📱 MEF Portal - Mobile Testing Guide

## ✅ Server is Running!

Your MEF Portal is now accessible from your mobile device!

---

## 📱 **ON YOUR MOBILE PHONE:**

### Open your browser and go to:

```
http://192.168.43.173:5000
```

---

## 💻 **ON THIS COMPUTER:**

You can also access it at:
- http://localhost:5000
- http://127.0.0.1:5000
- http://192.168.43.173:5000

---

## ✅ **IMPORTANT CHECKLIST:**

1. ✓ **Your phone MUST be on the SAME WiFi network** as this computer
   - Check your WiFi settings on both devices
   - Both should show the same network name

2. ✓ **Windows Firewall** needs to allow port 5000
   - If connection fails, run the firewall setup (see below)

3. ✓ **Use WiFi, NOT mobile data** on your phone

---

## 🔥 **IF CONNECTION FAILS - Firewall Setup:**

### Option 1: Run the automated script
1. Right-click PowerShell and select "Run as Administrator"
2. Navigate to this folder
3. Run: `.\setup_firewall.ps1`

### Option 2: Manual command
Run this in PowerShell AS ADMINISTRATOR:

```powershell
New-NetFirewallRule -DisplayName "Flask Port 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

---

## 🚀 **HOW TO START THE SERVER:**

Simply run:
```bash
python app.py
```

The server will automatically start on `0.0.0.0:5000` which makes it accessible from other devices.

---

## 📱 **TESTING RESPONSIVE DESIGN:**

Once connected on your mobile:
1. Test all pages (login, register, dashboard, etc.)
2. Check if menus work properly on small screens
3. Test touch interactions (buttons, forms, navigation)
4. Verify images and layouts adjust to screen size
5. Test in both portrait and landscape modes

---

## 🛑 **TO STOP THE SERVER:**

Press `CTRL+C` in the terminal

---

## 🔍 **TROUBLESHOOTING:**

### Can't connect from phone?

1. **Verify both devices on same WiFi:**
   - Computer: Run `ipconfig` and check "Wireless LAN adapter Wi-Fi"
   - Phone: Check WiFi settings

2. **Test from computer first:**
   - Open browser on computer
   - Go to http://192.168.43.173:5000
   - If this doesn't work, the firewall is blocking it

3. **Firewall issues:**
   - Run the firewall setup command (see above)
   - Or temporarily disable Windows Firewall to test

4. **Wrong IP address:**
   - Your IP might have changed
   - Run `ipconfig` to get current IP
   - Use the IPv4 Address from "Wireless LAN adapter Wi-Fi"

5. **Port already in use:**
   - Another program might be using port 5000
   - Close other Flask apps or change the port

---

## 📝 **CURRENT SERVER STATUS:**

```
✓ Server Running: YES
✓ Port: 5000
✓ Your IP: 192.168.43.173
✓ Access URL: http://192.168.43.173:5000
✓ Mobile Access: ENABLED
```

---

## 🎨 **Testing Mobile Responsiveness:**

Key areas to test:
- ✓ Navigation menu (hamburger menu on mobile)
- ✓ Forms (register, login, request forms)
- ✓ Tables (status page, admin dashboards)
- ✓ Buttons and touch targets (minimum 44x44px)
- ✓ Text readability (font sizes)
- ✓ Images and icons
- ✓ Cards and layouts

---

**Happy Testing! 🚀**
