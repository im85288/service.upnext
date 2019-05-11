import xbmc
import resources.lib.utils as utils
from resources.lib.api import Api
from resources.lib.developer import Developer
from resources.lib.state import State


# service class for playback monitoring
class Player(xbmc.Player):
        last_file = None

    def __init__(self):
        self.api = Api()
        self.developer = Developer()
        xbmc.Player.__init__(self)

    def set_last_file(self, file):
        self.last_file = file

    def get_last_file(self):
        return self.last_file

    def onPlayBackStarted(self):
        # Will be called when kodi starts playing a file
        self.api.reset_addon_data()
        if utils.settings("developerMode") == "true":
            self.developer.developer_play_back()

    def onPlayBackStopped(self):
        # Will be called when user stops playing a file.
        self.last_file = None
        self.api.reset_addon_data()
        State() # reset state
