This addon can be configured to show a popup next up notification automatically to prompt for playing the next unwatched episode.

Configuration:

  - The addon is found in the services section and allows the notification time to be adjusted (default 30 seconds before the end)
  - The default action (ie Play/Do not Play) when nothing is pressed can also be configured
  - The number of episodes played in a row with no intervention to bring up the still watching window can be adjusted.                                      

Skinners:
  
  - There is a script-upnext-upnext.xml and script-upnext-stillwatching.xml file located in default/1080i/ simply copy this to your skin folder and adjust it how you like it. 
  
      - script-upnext-upnext.xml
          - 3012 - Watch Now Button
          - 3013 - Cancel Button
          
      - script-nextup-notification-StillWatchingInfo.xml
          - 4012 - Continue Watching Button
          - 4013 - Cancel Button
          
      - Various Window Propertys are available including
          - Window.Property(fanart) - tvshow fanart
          - Window.Property(clearlogo) - tvshow clearlogo
          - Window.Property(clearart) - tvshow banner
          - Window.Property(landscape) - tvshow landscape
          - Window.Property(poster) - tvshow poster
          - Window.Property(thumb) - thumb
          - Window.Property(plot) - episode plot
          - Window.Property(tvshowtitle) - episode tvshow title
          - Window.Property(title) - episode title
          - Window.Property(season) - episode season number
          - Window.Property(episode) - episode episode number
          - Window.Property(year) - episode preimiered year
          - Window.Property(rating) - episode rating
          - Window.Property(duration) - episode duration
          - Window.Property(seasonepisode) - season/episode
          - Window.Property(playcount) - playcount
          - Window.Property(label) - label
          - Window.Property(simplemode) - when this is set, display simple mode versions of the windows
                 