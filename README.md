source code for shuttercycle.com

derived from:
http://tympanus.net/codrops/2010/06/24/multimedia-gallery/
by Mary Lou

ADDED FEATURES:
- medium + large image viewing modes
- large view has smooth mouse scrolling
- all image sizes (thumbs, medium, large) should be pre-generated
   . this is more efficient than dynamic scaling of large source images
   . medium image display still scales dynamically with browser window
- EXIF data display
- organize images by nested folders
- URLs to provide links to folders: myphotos.com/?gallery=PublicFolder 
- link to hidden folders: myphotos.com/?share=HiddenFolder
- python script to add images/folders to gallery (make_shuttercycle.py)
   . generates thumbnail, medium, large images
   . will extract EXIF


The source is a bit messy but it works...
