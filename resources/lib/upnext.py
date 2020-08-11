from utils import event

def send_signal(sender, next_info):
    """Helper function for plugins to send up next data to UpNext"""
    event(sender=sender + '.SIGNAL', message='upnext_data', data=next_info, encoding='base64')
