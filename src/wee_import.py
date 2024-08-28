import sys

description = """Shim utility to point users at the v5
weectl command and pertinent documentation."""


# ===============================================================================
#                       Main entry point
# ===============================================================================

def main():
    print()
    print("#######################################################")
    print("#                                                     #")
    print("# ERROR - command replaced with 'weectl' as of weewx  #")
    print("#         version 5.0 - for more information, see the #")
    print("#         Upgrade and Utilities guides for details.   #")
    print("#                                                     #")
    print("#######################################################")
    print()
    sys.exit(1)
    

if __name__ == "__main__":
    # Start up the program
    main()
