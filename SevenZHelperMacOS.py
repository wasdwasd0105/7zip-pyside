import base64
import struct
import sys
import objc

from Cocoa import NSPasteboard, NSPasteboardItem
from Foundation import NSURL, NSString, NSAppleEventManager, NSApplication, NSObject
from AppKit import NSWorkspace
from PySide6.QtWidgets import QMessageBox
from objc._pycoder import NSData


def copy_files_to_clipboard(file_paths):
    # Get the general pasteboard
    pasteboard = NSPasteboard.generalPasteboard()

    # Clear the current contents of the pasteboard
    pasteboard.clearContents()

    # Create a list to hold the pasteboard items
    pasteboard_items = []

    for file_path in file_paths:
        # Create a new pasteboard item
        pasteboard_item = NSPasteboardItem.alloc().init()

        # Create NSURL from file path
        file_url = NSURL.fileURLWithPath_(file_path)

        # Set the URL of the pasteboard item
        pasteboard_item.setString_forType_(str(file_url.absoluteString()), "public.file-url")

        # Add the pasteboard item to the list
        pasteboard_items.append(pasteboard_item)

    # Write the pasteboard items to the pasteboard
    pasteboard.writeObjects_(pasteboard_items)


def reveal_in_finder(file_path):
    if sys.platform == "darwin":
        url = NSURL.fileURLWithPath_(file_path)
        NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_([url])


def create_bookmark(path):
    url = NSURL.fileURLWithPath_(path)
    result_tuple = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
        1 << 11,  # NSURLBookmarkCreationWithSecurityScope
        None,
        None,
        None
    )
    bookmark_data = result_tuple[0]

    if bookmark_data:
        byte_array = bookmark_data.bytes().tobytes()  # Convert the NSData to a Python bytes-like object
        encoded_data = base64.b64encode(byte_array)  # Encode to base64
        return encoded_data.decode('utf-8')  # Convert the base64 bytes to string and return
    return None


def resolve_bookmark(encoded_data):
    # Decode the base64 string to get the raw data
    byte_array = base64.b64decode(encoded_data)

    # Convert the Python bytes-like object to an NSData object
    data_obj = NSData.dataWithBytes_length_(byte_array, len(byte_array))

    # Placeholder for potential error
    error = None

    # Try to resolve the bookmark
    resolved_url, is_stale, error = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
        data_obj,
        1 << 10,  # NSURLBookmarkResolutionWithSecurityScope
        None,
        None,
        error
    )

    # If there's an error or if the URL couldn't be resolved, return None
    if error or not resolved_url:
        return None



    return resolved_url.path()


def start_accessing_resource(encoded_data):
    # Decode the base64 string to get the raw data
    byte_array = base64.b64decode(encoded_data)

    # Convert the Python bytes-like object to an NSData object
    data_obj = NSData.dataWithBytes_length_(byte_array, len(byte_array))

    # Placeholder for potential error
    error = None

    # Try to resolve the bookmark to get the NSURL object
    resolved_url, is_stale, error = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
        data_obj,
        1 << 10,  # NSURLBookmarkResolutionWithSecurityScope
        None,
        None,
        error
    )

    # If there's an error or if the URL couldn't be resolved, return False
    if error or not resolved_url:
        return False

    # Start accessing the security-scoped resource
    res = resolved_url.startAccessingSecurityScopedResource()
    return res


def stop_accessing_resource(encoded_data):
    # Decode the base64 string to get the raw data
    byte_array = base64.b64decode(encoded_data)

    # Convert the Python bytes-like object to an NSData object
    data_obj = NSData.dataWithBytes_length_(byte_array, len(byte_array))

    # Placeholder for potential error
    error = None

    # Try to resolve the bookmark to get the NSURL object
    resolved_url, is_stale, error = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
        data_obj,
        1 << 10,  # NSURLBookmarkResolutionWithSecurityScope
        None,
        None,
        error
    )

    # If there's an error or if the URL couldn't be resolved, return False
    if error or not resolved_url:
        return False

    # Start accessing the security-scoped resource
    res = resolved_url.stopAccessingSecurityScopedResource()
    return res
