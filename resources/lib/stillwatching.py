from platform import machine

import xbmc
import xbmcgui


ACTION_PLAYER_STOP = 13
OS_MACHINE = machine()


class StillWatching(xbmcgui.WindowXMLDialog):
    item = None
    cancel = False
    stillwatching = False

    def __init__(self, *args, **kwargs):
        self.action_exitkeys_id = [10, 13]
        if OS_MACHINE[0:5] == 'armv7':
            xbmcgui.WindowXMLDialog.__init__(self)
        else:
            xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.setInfo()

    def setInfo(self):

        if self.item is not None:
            self.setProperty(
                'fanart', self.item['art'].get('tvshow.fanart', ''))
            self.setProperty(
                'landscape', self.item['art'].get('tvshow.landscape', ''))
            self.setProperty(
                'clearart', self.item['art'].get('tvshow.clearart', ''))
            self.setProperty(
                'poster', self.item['art'].get('tvshow.poster', ''))
            self.setProperty(
                'thumb', self.item['art'].get('thumb', ''))
            self.setProperty(
                'plot', self.item['plot'])
            self.setProperty(
                'tvshowtitle', self.item['showtitle'])
            self.setProperty(
                'title', self.item['title'])
            self.setProperty(
                'season', str(self.item['season']))
            self.setProperty(
                'episode', str(self.item['episode']))
            self.setProperty(
                'year', str(self.item['firstaired']))
            self.setProperty(
                'rating', str(round(float(self.item['rating']), 1)))
            self.setProperty(
                'duration', str(self.item['runtime'] / 60))
            self.setProperty(
                'playcount', str(self.item['playcount']))
            self.setProperty(
                'label', str(self.item['label']))

    def setItem(self, item):
        self.item = item

    def setCancel(self, cancel):
        self.cancel = cancel

    def isCancel(self):
        return self.cancel

    def setStillWatching(self, stillwatching):
        self.stillwatching = stillwatching

    def isStillWatching(self):
        return self.stillwatching

    def onFocus(self, controlId):
        pass

    def doAction(self):
        pass

    def closeDialog(self):
        self.close()

    def onClick(self, controlID):

        xbmc.log("still watching info onclick: " + str(controlID))

        if controlID == 4012:
            # still watching
            self.setStillWatching(True)
            self.close()
        elif controlID == 4013:
            # cancel
            self.setCancel(True)
            self.close()
        pass

    def onAction(self, action):
        xbmc.log("still watching info action: " + str(action.getId()))
        if action == ACTION_PLAYER_STOP:
            self.close()

