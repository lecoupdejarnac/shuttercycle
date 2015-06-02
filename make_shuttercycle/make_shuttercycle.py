from __future__ import division

import json
import fileinput
import os.path
import re
import shutil
import sys

from iptcinfo import IPTCInfo
from PIL import Image
from PIL.ExifTags import TAGS

SITE_ROOT = ''
SHARE_PATH = ''
CONVERT_CMD = ''
TMP_PATH = os.getcwd() + '/tmp'
if sys.platform == 'win32':
    SHARE_PATH = 'Y:/shuttercycle_pics/'
    SITE_ROOT = 'Z:/www'
    # uses imagemagic's convert utility
    # renamed convert.exe to im_convert.exe on Win7 - it already has a 'convert' utility
    #CONVERT_CMD = 'convert "%s" -resize %dx%d "%s"'
    CONVERT_CMD = 'im_convert "%s" -resize %dx%d "%s"'
elif sys.platform == 'darwin':
    SITE_ROOT = '/Volumes/storage/www'
    SHARE_PATH = '/Volumes/share/shuttercycle_pics/'
    # uses vipsthumbnail (part of libvips)
    # faster and imagemagick gave unsharp results on mac
    # use -p option to set interpolator: good options are [bilinear, bicubic, lbb, nohalo]
    CONVERT_CMD = 'vipsthumbnail "%s" -s %dx%d -o "%s[no_subsample]" --interpolator=nohalo --sharpen=none'
else:
    raise Exception("Unsupported platform")

CONFIG_PATH = SITE_ROOT + '/configs/'
ERRORS_PATH = SITE_ROOT + '/errors/'
PHOTOS_PATH = SITE_ROOT + '/media/photos/'
NEW_ITEM_PATH = TMP_PATH + '/new/'
LOCKFILE = NEW_ITEM_PATH + '.lock'
MAIN = '_main_/'
HIDDEN = 'hidden/'
GALLERY = 'gallery/'
PROCESS_NAME = 'make_shuttercycle.exe'
THUMB_EXT = 'THMB'
MEDIUM_EXT = 'MED'
LARGE_EXT = 'LG'
BACKUP_EXT = 'BK'
CONFIG_FILE = 'config.json'
MAIN_GALLERY_CONFIG_PATH = CONFIG_PATH + GALLERY + CONFIG_FILE
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


def _load_config(config_path):
    file = open(config_path, 'r')
    result = json.load(file)
    file.close()
    return result


main_config = _load_config(MAIN_GALLERY_CONFIG_PATH)


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
        os.makedirs(path + folder)
        __debug('created folder %s' % path + folder)


def _setup_image_folders(folder):
    _create_nonexistent_folder(SHARE_PATH, folder)


def _imagemagick_resize(source, dest_path, dest_filename, max_dimension):
    tmp_path = TMP_PATH + "/" + dest_filename
    # renamed convert.exe to im_convert.exe on Win7 - it already has a 'convert' utility
    #cmd = 'convert "%s" -resize %dx%d "%s"' % (source, max_dimension, max_dimension, dest)
    cmd = CONVERT_CMD % (source, max_dimension, max_dimension, tmp_path)
    print 'running {%s}' % cmd
    os.system(cmd)
    _move_to_photo_folder(tmp_path, dest_path)


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
    accession = _get_accession(source_file)
    dest_path = _get_image_path(accession, current_folder, LARGE_EXT)
    large_filename = accession  + '.' + LARGE_EXT + JPEG_EXT
    extent = LARGE_MAX_EXTENT
    if _is_image_xtra_large(source_location):
        extent = XLARGE_MAX_EXTENT
    _imagemagick_resize(source_location, dest_path, large_filename, extent)
    __debug('large: %s' % dest_path)


def _create_med_image(source_file, source_location, current_folder):
    accession = _get_accession(source_file)
    dest_path = _get_image_path(accession, current_folder, MEDIUM_EXT)
    med_filename = accession  + '.' + MEDIUM_EXT + JPEG_EXT
    extent = MED_MAX_EXTENT
    if _is_image_xtra_large(source_location):
        extent = XMED_MAX_EXTENT
    _imagemagick_resize(source_location, dest_path, med_filename, extent)
    __debug('med: %s' % dest_path)


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
        os.makedirs(scaled_dir)
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


def _move_to_photo_folder(tmp_path, dest_path):
    __debug('moving from "%s" to "%s"' % (tmp_path, dest_path))
    shutil.move(tmp_path, dest_path)


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


def _add_folder_to_config(folder_name, config):
    node = {\
        'type': 'folder',\
        'img_thumb': '',\
        'source': folder_name,\
        'description': folder_name\
    }
    # prepend new folders to the config
    config.insert(0, node)


def _write_config(config, config_path):
    shutil.copy(config_path, config_path + CONFIG_BACKUP_EXT)
    _delete_file(config_path)
    file = open(config_path, 'w')
    json.dump(config, file, sort_keys=True, indent=4, separators=(',', ': '))
    file.close()
    __debug('wrote config %s' % config_path)


def _create_metadata(exif):
    camera = _get_image_camera(exif)
    lens = _get_image_lens(exif)
    focal_length = _get_image_focal_length(exif)
    iso = _get_image_iso(exif)
    shutter_speed = _get_image_shutter_speed(exif)
    aperture = _get_image_aperture(exif)

    if not (camera or lens or focal_length or iso or shutter_speed or aperture):
        return None

    meta = {}
    if camera: meta['camera'] = camera
    if lens: meta['lens'] = lens
    if focal_length: meta['lens'] = lens
    if iso: meta['iso'] = iso
    if shutter_speed: meta['shutter_speed'] = shutter_speed
    if aperture: meta['aperture'] = aperture
    return meta


def _replace_meta(oldData, newData, name):
    for key, value in newData.items():
        oldData[key] = value


def _merge_metadata(newMeta, oldMeta):
    if not oldMeta:
        return newMeta

    if not newMeta:
        return oldMeta

    _replace_meta(oldMeta, newMeta, 'camera')
    _replace_meta(oldMeta, newMeta, 'lens')
    _replace_meta(oldMeta, newMeta, 'focal_length')
    _replace_meta(oldMeta, newMeta, 'iso')
    _replace_meta(oldMeta, newMeta, 'shutter_speed')
    _replace_meta(oldMeta, newMeta, 'aperture')
    return oldMeta


def _add_image_to_config(image, exif, iptc, config, config_images, current_folder):
    node = {\
        'type': 'photo',\
        'img_thumb': image,\
        'img_medium': image,\
        'img_large': image\
    }

    description = _get_image_caption(iptc)
    if description: node['description'] = description

    index = len(config)
    meta = _create_metadata(exif)
    if image in config_images:
        existing = config_images[image]
        meta = _merge_metadata(meta, existing['meta'])
        if meta: node['meta'] = meta

        index = existing['index']
        config[index] = node
        __debug('   replaced %s in %s config' % (image, current_folder))
    else:
        if meta: node['meta'] = meta
        config.append(node)
        __debug('   added %s to %s config' % (image, current_folder))
    copy = dict(node)
    copy['index'] = index
    config_images[image] = copy


def _get_config_file_path(folder):
    return CONFIG_PATH + folder + CONFIG_FILE


def _setup_configs(current_folder, new):
    folder = CONFIG_PATH + current_folder + new
    if not os.path.isdir(folder):
        os.makedirs(folder)
        __debug('created folder %s' % folder)

    config_file = folder + '/' + CONFIG_FILE
    if not os.path.isfile(config_file):
        file = open(config_file, 'w')
        file.write('[]')
        file.close()
        __debug('created file %s' % config_file)


def _delete_file(path):
    os.remove(path)
    __debug('deleted file %s' % path)


def _get_config_images(config):
    config_images = {}
    for i in range(0, len(config)):
        entry = config[i]
        if entry['type'] == 'photo':
            copy = dict(entry)
            copy['index'] = i
            config_images[entry['img_thumb']] = copy

    return config_images


def _process_new_files(current_folder):
    items = os.listdir(NEW_ITEM_PATH + current_folder)
    if not items:
        return

    config = None
    config_path = ''
    if current_folder == (GALLERY + MAIN):
        config_path = MAIN_GALLERY_CONFIG_PATH
        config = main_config
    else:
        config_path = _get_config_file_path(current_folder)
        config = _load_config(config_path)

    # skip the GALLERY folder, because its images are really in GALLERY+MAIN
    if current_folder != GALLERY:
        config_images = _get_config_images(config)

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
                _add_folder_to_config(item, config)
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
            _add_image_to_config(item, exif, iptc, config, config_images, current_folder)
            dirty_config = True
            added_file_paths.add(current_folder + item)
            __debug('DONE image')

    if dirty_config:
        _write_config(config, config_path)
        added_file_paths.add(current_folder + CONFIG_FILE)


def _is_already_running():
    if not os.path.isfile(LOCKFILE):
        #XXX this is prone to races: multiple procs can get here at the same time!
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
