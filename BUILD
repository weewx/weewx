   1. Check to make sure weewx.conf doesn't have any local changes. In particular, check to make sure:
         1. WEEWX_ROOT points to /home/weewx
         2. Debug set to zero.
   2. Make sure the correct version has been entered in weewx.__init__.py
   3. Make sure the correct version has been entered in weewx.conf.
   4. Make sure all changes have been logged in README.txt.
   5. Make sure the upgrading guide has been updated if necessary.
   6. Make sure the customizing.htm and usersguide.htm have the correct version number at the top.
   7. If working off a branch, commit all changes.
   8. Switch to main trunk
   9. Right click on the top level weewx, select Team | Merge. Select "Reintegrate" and enter the branch as the URL. 
  10. After looking things over, commit changes back to the trunk.
  11. Right click top level weewx, select Team | Tag and create a new tag with a name similar to tags/v1.3.1.  Comment should read something like "Version 1.3.1 release"
  12. Using a terminal, run "./setup.py sdist" to create a tarball.
  13. As a final sanity check, go to the production machine, unpack the tarball, install, run.
  14. Uploading to SourceForge:
         1. Upload tarball
         2. Select the new tarball as the Mac, Linux, and BSD distribution
  15. Run a backup on Raven
  16. Run Microsoft Expression Web on the PC.
         1. Copy all the new docs to the weewx web folder, subdirectory docs.
         2. Add to the "What's New" section on the front page.
         3. Upload everything to the web server.
  17. Announce the release to the weewx user's group.
