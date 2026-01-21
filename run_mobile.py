#!/usr/bin/env python3
"""
MEF Portal - Mobile Testing Runner
Run this to test the portal on your mobile device
"""

import socket
import sys
import os

def get_local_ip():
    """Get the local IP address of this computer"""
    try:
        # Create a socket connection to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        return None

def print_instructions(local_ip):
    """Print mobile testing instructions"""
    print("\n" + "="*70)
    print("🚀 MEF PORTAL - MOBILE TESTING MODE")
    print("="*70)
    
    if local_ip:
        print(f"\n📱 ON YOUR MOBILE PHONE:")
        print(f"   Open your browser and go to:")
        print(f"\n   ➡️  http://{local_ip}:5000")
        print(f"\n💻 ON THIS COMPUTER:")
        print(f"   http://localhost:5000")
        print(f"   http://127.0.0.1:5000")
        print(f"   http://{local_ip}:5000")
    else:
        print("\n⚠️  Could not determine IP address")
        print("   Run 'ipconfig' and use the IPv4 Address manually")
    
    print("\n" + "-"*70)
    print("✅ CHECKLIST - Make sure:")
    print("   1. ✓ Your phone is on the SAME WiFi network as this computer")
    print("   2. ✓ Windows Firewall allows port 5000 (see instructions below)")
    print("   3. ✓ Both devices are connected to WiFi (not mobile data)")
    print("\n" + "-"*70)
    print("🔥 FIREWALL SETUP (If connection fails):")
    print("   Run PowerShell AS ADMINISTRATOR and execute:")
    print('\n   New-NetFirewallRule -DisplayName "Flask Port 5000" `')
    print('       -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow')
    print("\n" + "="*70)
    print("\n⏳ Starting server... Press CTRL+C to stop\n")

def main():
    """Main function to start the server"""
    # Get local IP
    local_ip = get_local_ip()
    
    # Print instructions
    print_instructions(local_ip)
    
    # Import and run the Flask app directly from app.py file
    try:
        import sys
        import os
        
        # Make sure we can import from current directory
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Import directly from app.py module (not the app package)
        import app as app_module
        
        # Initialize database
        with app_module.app.app_context():
            app_module.init_db()
        
        # Run server on all interfaces (accessible from mobile)
        app_module.app.run(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("Make sure you're in the correct directory with app.py")
        sys.exit(1)

if __name__ == "__main__":
    main()
