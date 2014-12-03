from __future__ import division

import fileinput
import os.path
import re
import shutil
import sys
import wmi
import xml.dom.minidom as minidom

from iptcinfo import IPTCInfo
from PIL import Image
from PIL.ExifTags import TAGS

SITE_ROOT = 'Z:/www'
CONFIG_PATH = SITE_ROOT + '/configs/'
ERRORS_PATH = SITE_ROOT + '/errors/'
PHOTOS_PATH = SITE_ROOT + '/media/photos/'
NEW_ITEM_PATH = SITE_ROOT + '/new/'
LOCKFILE = NEW_ITEM_PATH + '.lock'
MAIN = '_main_/'
HIDDEN = 'hidden/'
GALLERY = 'gallery/'
SHARE_PATH = 'Y:/shuttercycle_pics/'
PROCESS_NAME = 'make_shuttercycle.exe'
THUMB_EXT = 'THMB'
MEDIUM_EXT = 'MED'
LARGE_EXT = 'LG'
BACKUP_EXT = 'BK'
CONFIG_FILE = 'config.xml'
JPEG_EXT = '.jpg'
CONFIG_BACKUP_EXT = '.bkup'
DEBUG_OUTPUT = True
XLARGE_MAX_EXTENT = 3500
LARGE_MAX_EXTENT = 1200
XMED_MAX_EXTENT = 1200
MED_MAX_EXTENT = 800
THUMB_MAX_EXTENT = 130
CAPTION_KEY = 'caption/abstract'
CAMERA_KEY = 'Model'
LENS_KEY = 42036
ISO_KEY = 'ISOSpeedRatings'
FOCAL_KEY = 'FocalLength'
SHUTTER_KEY = 'ExposureTime'
APERTURE_KEY = 'FNumber'
ADDED_FILES = NEW_ITEM_PATH + 'added_files.txt'

added_file_paths = set()
main_dom = None
main_config_dirty = False

fix_xml = re.compile(r'((?<=>)(\n[\t]*)(?=[^<\t]))|(?<=[^>\t])(\n[\t]*)(?=<)')
fix_xml2 = re.compile('\s*$', re.MULTILINE)

# courtesy: http://ronrothman.com/public/leftbraned/xml-dom-minidom-toprettyxml-and-silly-whitespace/
def fixed_writexml(self, writer, indent="", addindent="", newl=""):
    # indent = current indentation
    # addindent = indentation to add to higher levels
    # newl = newline string
    writer.write(indent+"<" + self.tagName)

    attrs = self._get_attributes()
    a_names = attrs.keys()
    a_names.sort()

    for a_name in a_names:
        writer.write(" %s=\"" % a_name)
        minidom._write_data(writer, attrs[a_name].value)
        writer.write("\"")
    if self.childNodes:
        if len(self.childNodes) == 1 \
          and self.childNodes[0].nodeType == minidom.Node.TEXT_NODE:
            writer.write(">")
            self.childNodes[0].writexml(writer, "", "", "")
            writer.write("</%s>%s" % (self.tagName, newl))
            return
        writer.write(">%s"%(newl))
        for node in self.childNodes:
            node.writexml(writer,indent+addindent,addindent,newl)
        writer.write("%s</%s>%s" % (indent,self.tagName,newl))
    else:
        writer.write("/>%s"%(newl))
# replace minidom's function with ours
minidom.Element.writexml = fixed_writexml


# courtesy: http://www.blog.pythonlibrary.org/2010/03/28/getting-photo-metadata-exif-using-python/
def get_exif(filename):
    ret = {}
    i = Image.open(filename)
    info = i._getexif()
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        ret[decoded] = value
    return ret


def __debug(msg):
    if DEBUG_OUTPUT:
        print msg


def __replace_string(input, old, new):
    if input == old:
        return new
    return input


def _get_accession(filename):
    return filename[:filename.rfind('.')]


def _get_extension(filename):
    return filename[filename.rfind('.'):]


def _get_image_path(accession, current_folder, size):
    return PHOTOS_PATH + current_folder + accession + "." + size + JPEG_EXT


def _get_thumb_path(accession, current_folder):
    return _get_image_path(accession, current_folder, THUMB_EXT)


def _get_medium_path(accession, current_folder):
    return _get_image_path(accession, current_folder, MEDIUM_EXT)


def _get_large_path(accession, current_folder):
    return _get_image_path(accession, current_folder, LARGE_EXT)


def _get_side_preserve_aspect(old_value, old_other_side, new_other_side):
    return int(old_value * (float(new_other_side) / float(old_other_side)))


def _get_image_caption(info):
    try:
        caption = info.data[CAPTION_KEY]
        caption = __replace_string(caption, 'OLYMPUS DIGITAL CAMERA', '')
        return caption
    except KeyError:
        return ''


def _get_image_camera(info):
    try:
        camera = info[CAMERA_KEY]
        camera = __replace_string(camera, 'XZ-1', 'Olympus XZ-1')
        return camera
    except KeyError:
        return ''


def _get_image_lens(info):
    try:
        lens = info[LENS_KEY]
        lens = __replace_string(lens, '18-270mm', 'Tamron 18-270mm f/3.5-6.3 Di II VC PZD')
        return lens
    except KeyError:
        return ''


def _get_image_focal_length(info):
    try:
        return str(info[FOCAL_KEY][0]) + 'mm'
    except KeyError:
        return ''


def _get_image_iso(info):
    try:
        return str(info[ISO_KEY])
    except KeyError:
        return ''


def _get_image_shutter_speed(info):
    try:
        n = int(info[SHUTTER_KEY][0])
        d = int(info[SHUTTER_KEY][1])
        if n > d:
            return '%d s' % (n / d)
        else:
            return '%d/%d s' % (n, d)
    except KeyError:
        return ''


def _get_image_aperture(info):
    try:
        #XXX what if its not returned as a two-tuple?
        return 'f/%.1f' % (float(info[APERTURE_KEY][0]) / float(info[APERTURE_KEY][1]))
    except KeyError:
        return ''


def _get_new_size(img, max_extent):
    width = img.size[0]
    height = img.size[1]
    if width > height:
        new_width = max_extent
        new_height = _get_side_preserve_aspect(height, width, new_width)
        return (new_width, new_height)
    else:
        new_height = max_extent 
        new_width = _get_side_preserve_aspect(width, height, new_height)
        return (new_width, new_height)


def _create_nonexistent_folder(path, folder):
    if not os.path.isdir(path + folder):
        os.mkdir(path + folder)
        __debug('created folder %s' % path + folder)


def _setup_image_folders(folder):
    _create_nonexistent_folder(SHARE_PATH, folder)


def _imagemagick_resize(source, dest, max_dimension):
    # renamed convert.exe to im_convert.exe on Win7 - it already has a 'convert' utility
    #cmd = 'convert "%s" -resize %dx%d "%s"' % (source, max_dimension, max_dimension, dest)
    cmd = 'im_convert "%s" -resize %dx%d "%s"' % (source, max_dimension, max_dimension, dest)
    print 'running {%s}' % cmd
    os.system(cmd)


def _is_image_xtra_large(source_location):
    img = Image.open(source_location)
    width = img.size[0]
    height = img.size[1]
    if width > 6000 or height > 6000:
        __debug('   (is extra large image CASE 1)')
        return True
#XXX for higher MP images, this will always return True
#    if width + height > 9000:
#        __debug('   (is extra large image CASE 2)')
#        return True

    if width > height and width / height > 2.5:
        __debug('   (is extra large image CASE 3)')
        return True
    elif height / width > 2.5:
        __debug('   (is extra large image CASE 4)')
        return True

    return False


def _create_large_image(source_file, source_location, current_folder):
    large_path = _get_large_path(_get_accession(source_file), current_folder)
    extent = LARGE_MAX_EXTENT
    if _is_image_xtra_large(source_location):
        extent = XLARGE_MAX_EXTENT
    _imagemagick_resize(source_location, large_path, extent)
    __debug('large: %s' % large_path)


def _create_med_image(source_file, source_location, current_folder):
    med_path = _get_medium_path(_get_accession(source_file), current_folder)
    extent = MED_MAX_EXTENT
    if _is_image_xtra_large(source_location):
        extent = XMED_MAX_EXTENT
    _imagemagick_resize(source_location, med_path, extent)
    __debug('med: %s' % med_path)


def _create_thumbnail(source_location, thumb_path):
    img = Image.open(source_location)
    thumb = img.resize(_get_new_size(img, THUMB_MAX_EXTENT), Image.ANTIALIAS)
    thumb.save(thumb_path, 'JPEG')
    __debug('thumb: %s' % thumb_path)


def _do_create_sized_images(source_file, current_folder):
    result = True
    source_location = NEW_ITEM_PATH + current_folder + source_file
    thumb_path = _get_thumb_path(_get_accession(source_file), current_folder)
    scaled_dir = PHOTOS_PATH + current_folder
    if not os.path.isdir(scaled_dir):
        os.mkdir(scaled_dir)
        __debug('created folder %s' % scaled_dir)
    elif os.path.isfile(thumb_path):
        __debug('WARNING: %s will be REPLACED' % (current_folder + source_file))
        shutil.copy(source_location, ERRORS_PATH + source_file)
        result = False

    _create_large_image(source_file, source_location, current_folder)

    _create_med_image(source_file, source_location, current_folder)

    _create_thumbnail(source_location, thumb_path)

    return result


def _copy_to_share_folder(new_path, image, folder):
    shutil.copy(new_path, SHARE_PATH + folder + image)


def _move_to_backup_folder(new_path, image, folder):
    backup = PHOTOS_PATH + folder + _get_accession(image) + "." + BACKUP_EXT + JPEG_EXT
    if os.path.isfile(backup):
        os.remove(backup)
    shutil.move(new_path, backup)


def _create_sized_images(image, current_folder):
    result = _do_create_sized_images(image, current_folder)
    new_path = NEW_ITEM_PATH + current_folder + image 
    _copy_to_share_folder(new_path, image, current_folder)
#    _move_to_backup_folder(new_path, image, current_folder)
    os.unlink(new_path)
    return result


def _get_folder_xml(name):
    return '   <file type="folder">\n'\
           '      <thumb></thumb>\n'\
           '      <source>%s</source>\n'\
           '      <description>%s</description>\n'\
           '   </file>' % (name, name)


def _append_folder_to_config(config_file, folder_name):
    finput = fileinput.FileInput(config_file, inplace=1)

    for line in finput:
        if '<MultimediaGallery>' in line:
            line = line + _get_folder_xml(folder_name)
        print line.rstrip()


def _append_child_tag(node, tag, value, attr=None, attr_val=None):
    text = minidom.Text()
    text.data = value
    child = minidom.Element(tag)
    child.appendChild(text)

    if attr:
        child.setAttribute(attr, attr_val)
        
    node.appendChild(child)


def _get_gallery_element(dom):
    return dom.getElementsByTagName('MultimediaGallery')[0]


def _append_folder_to_dom(folder_name, dom):
    node = minidom.Element('file')
    node.setAttribute('type', 'folder')

    _append_child_tag(node, 'thumb', '')
    _append_child_tag(node, 'source', folder_name)
    _append_child_tag(node, 'description', folder_name)

    if _get_gallery_element(dom).firstChild:
        _get_gallery_element(dom).insertBefore(node, _get_gallery_element(dom).firstChild)
    else:
        _get_gallery_element(dom).appendChild(node)


def _write_dom_to_xml(dom, config_path):
    shutil.copy(config_path, config_path + CONFIG_BACKUP_EXT)
    _delete_file(config_path)
    file = open(config_path, 'w')
    output = re.sub(fix_xml, '', dom.toprettyxml())
    output = re.sub(fix_xml2, '', output)
    file.write(output)
    file.close()
    __debug('wrote xml %s' % config_path)


def _create_metadata(node, exif):
    camera = _get_image_camera(exif)
    lens = _get_image_lens(exif)
    focal_length = _get_image_focal_length(exif)
    iso = _get_image_iso(exif)
    shutter_speed = _get_image_shutter_speed(exif)
    aperture = _get_image_aperture(exif)

    if not (camera or lens or focal_length or iso or shutter_speed or aperture):
        return

    meta = minidom.Element('meta')
    _append_child_tag(meta, 'camera', camera)
    _append_child_tag(meta, 'lens', lens)
    _append_child_tag(meta, 'focal_length', focal_length)
    _append_child_tag(meta, 'iso', iso)
    _append_child_tag(meta, 'shutter_speed', shutter_speed)
    _append_child_tag(meta, 'aperture', aperture)
    return meta


def _replace_meta(oldData, newData, name):
    items = oldData.getElementsByTagName(name)
    if not items:
        return

    if items[0].getAttribute('locked'):
        newData.replaceChild(items[0], newData.getElementsByTagName(name)[0])


def _finalize_metadata(newMeta, oldMeta):
    if not oldMeta:
        return

    oldData = oldMeta[0]
    _replace_meta(oldData, newMeta, 'camera')
    _replace_meta(oldData, newMeta, 'lens')
    _replace_meta(oldData, newMeta, 'focal_length')
    _replace_meta(oldData, newMeta, 'iso')
    _replace_meta(oldData, newMeta, 'shutter_speed')
    _replace_meta(oldData, newMeta, 'aperture')


def _append_image_to_dom(image, exif, iptc, dom, config_images, current_folder):
    node = minidom.Element('file')
    node.setAttribute('type', 'photo')

    _append_child_tag(node, 'thumb', image)
    _append_child_tag(node, 'source', image, 'size', 'medium')
    _append_child_tag(node, 'source', image, 'size', 'large')
    _append_child_tag(node, 'description', _get_image_caption(iptc))
    metaNode = _create_metadata(node, exif)

    if image in config_images:
        _finalize_metadata(metaNode, config_images[image].getElementsByTagName('meta'))
        node.appendChild(metaNode)
        _get_gallery_element(dom).replaceChild(node, config_images[image])
        config_images[image].getElementsByTagName('description')
        __debug('   replaced %s in %s config' % (image, current_folder))
    else:
        node.appendChild(metaNode)
        _get_gallery_element(dom).appendChild(node)
        __debug('   added %s to %s config' % (image, current_folder))
    config_images[image] = node


def _get_config_file_path(folder):
    return CONFIG_PATH + folder + CONFIG_FILE


def _setup_configs(current_folder, new):
    folder = CONFIG_PATH + current_folder + new
    if not os.path.isdir(folder):
        os.mkdir(folder)
        __debug('created folder %s' % folder)

    config_file = folder + '/' + CONFIG_FILE
    if not os.path.isfile(config_file):
        file = open(config_file, 'w')
        file.write('<?xml version="1.0"?>\n<MultimediaGallery>\n</MultimediaGallery>')
        file.close()
        __debug('created file %s' % config_file)
    

def _delete_file(path):
    os.remove(path)
    __debug('deleted file %s' % path)


def _get_config_images(dom):
    config_images = {}
    files = dom.getElementsByTagName('file')
    for file in files:
        if file.getAttribute('type') == 'photo':
            thumbs = file.getElementsByTagName('thumb')
            if thumbs and thumbs[0].firstChild:
                config_images[thumbs[0].firstChild.data] = file
    return config_images


def _process_new_files(current_folder):
    items = os.listdir(NEW_ITEM_PATH + current_folder)
    if not items:
        return

    global main_dom
    dom = None
    config_path = ''
    if current_folder == (GALLERY + MAIN):
        config_path = CONFIG_PATH + GALLERY + CONFIG_FILE
        dom = main_dom
    else:
        config_path = _get_config_file_path(current_folder)
        dom = minidom.parse(config_path)

    config_images = {}
    if current_folder == GALLERY:
        main_dom = dom
    else:
        config_images = _get_config_images(dom)

    __debug('using config at %s' % config_path)
    dirty_config = False

    for item in items:
        filepath = NEW_ITEM_PATH + current_folder + item
        __debug('processing %s' % current_folder + item)

        if os.path.isfile(filepath) and _get_extension(item) == '.JPG':
            os.rename(filepath, _get_accession(item) + JPEG_EXT);

        if os.path.isdir(filepath):
            if not os.path.isdir(CONFIG_PATH + current_folder + item) and\
            current_folder != HIDDEN:
                _append_folder_to_dom(item, dom)
                dirty_config = True
                __debug('   added %s to %s config' % (item, config_path))
            _setup_configs(current_folder, item)
            _setup_image_folders(current_folder + item)
            _process_new_files(current_folder + item + '/')
            __debug('DONE folder')
        elif os.path.isfile(filepath) and _get_extension(item) == JPEG_EXT:
            iptc = IPTCInfo(filepath)
            exif = get_exif(filepath)
            _create_sized_images(item, current_folder)
            _append_image_to_dom(item, exif, iptc, dom, config_images, current_folder)
            dirty_config = True
            added_file_paths.add(current_folder + item)
            __debug('DONE image')

    global main_config_dirty
    if current_folder == (GALLERY + MAIN) and dirty_config:
        main_config_dirty = True
    elif dirty_config or (current_folder == GALLERY and main_config_dirty):
        _write_dom_to_xml(dom, config_path)
        added_file_paths.add(current_folder + CONFIG_FILE)


def _is_already_running():
    if not os.path.isfile(LOCKFILE):
        open(LOCKFILE, 'w')
        return False
#    count = 0
#    c = wmi.WMI()
#    for process in c.Win32_Process(Name=PROCESS_NAME):
#        count += 1
#        if count > 1:
#            return True
    return True 


def read_added_files(files):
    if not os.path.isfile(ADDED_FILES):
        return
    file = open(ADDED_FILES, 'r')
    for line in file:
        files.add(line)
    file.close()


def write_added_files(files):
    file = open(ADDED_FILES, 'w')
    for added in files:
        file.write(added + '\n')
    file.close()


def _output_added_files():
    read_added_files(added_file_paths)
    write_added_files(added_file_paths)


def main():
    if not _is_already_running():
        _setup_configs('', '')
        _process_new_files(GALLERY)
        _process_new_files(HIDDEN)
        _output_added_files()
        os.unlink(LOCKFILE)
        raw_input("DONE - Press ENTER.")
        return 0

    print 'make_shuttercycle ALREADY RUNNING - ABORTING'
    return 1


if __name__ == '__main__':
    sys.exit(main())
