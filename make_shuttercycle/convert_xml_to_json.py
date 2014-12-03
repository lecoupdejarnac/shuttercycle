
from __future__ import division

import fileinput
import json
import os.path
import re
import shutil
import sys
import xml.dom.minidom as minidom

SITE_ROOT = '/Volumes/storage/www'
CONFIG_PATH = SITE_ROOT + '/configs/'


def _delete_file(path):
    os.remove(path)
    print 'deleted file %s' % path


def _convert_to_json(dom):
    json_array = []
    files = dom.getElementsByTagName('file')
    for file in files:
        output = {}
        item_type = file.getAttribute('type')
        output['type'] = item_type

        thumbs = file.getElementsByTagName('thumb')
        if thumbs and thumbs[0].firstChild:
            output['img_thumb'] = thumbs[0].firstChild.data

        descriptions = file.getElementsByTagName('description')
        if descriptions and descriptions[0].firstChild:
            output['description'] = descriptions[0].firstChild.data

        sources = file.getElementsByTagName('source')
        if item_type == "photo":
            for source in sources:
                if source.getAttribute('size') == 'medium':
                    output['img_medium'] = source.firstChild.data
                if source.getAttribute('size') == 'large':
                    output['img_large'] = source.firstChild.data
        elif sources and sources[0].firstChild:
                output['source'] = sources[0].firstChild.data

        meta = file.getElementsByTagName('meta')
        if meta and len(meta) > 0:
            meta_output = {}
            cameras = meta[0].getElementsByTagName('camera')
            if cameras and cameras[0].firstChild:
                meta_output['camera'] = cameras[0].firstChild.data

            lens = meta[0].getElementsByTagName('lens')
            if lens and lens[0].firstChild:
                meta_output['lens'] = lens[0].firstChild.data

            focal_lengths = meta[0].getElementsByTagName('focal_length')
            if focal_lengths and focal_lengths[0].firstChild:
                meta_output['focal_length'] = focal_lengths[0].firstChild.data

            isos = meta[0].getElementsByTagName('iso')
            if isos and isos[0].firstChild:
                meta_output['iso'] = isos[0].firstChild.data

            shutter_speeds = meta[0].getElementsByTagName('shutter_speed')
            if shutter_speeds and shutter_speeds[0].firstChild:
                meta_output['shutter_speed'] = shutter_speeds[0].firstChild.data

            apertures = meta[0].getElementsByTagName('aperture')
            if apertures and apertures[0].firstChild:
                meta_output['aperture'] = apertures[0].firstChild.data

            if len(meta_output) > 0:
                output['meta'] = meta_output

        json_array.append(output)

    return json_array


def _convert_configs(current_folder):
    itempath = CONFIG_PATH + current_folder
    items = os.listdir(itempath)

    for item in items:
        filepath = itempath + item

        if os.path.isfile(filepath) and item == 'config.xml':
            print 'converting %s' % filepath
            dom = minidom.parse(filepath)
#            config_images = _get_config_images(dom)
            json_array = _convert_to_json(dom)
            output = json.dumps(json_array, sort_keys=True, indent=4, separators=(',', ': '))
            print output
            #XXX write json_dict to file as JSON
            outfile = open(itempath + 'config.json', 'w')
            outfile.write(output)
            outfile.close()
#            _delete_file(filepath)

        if os.path.isdir(filepath):
           _convert_configs(current_folder + item + "/")


def main():
    _convert_configs("")
    print 'DONE'
    return 1


if __name__ == '__main__':
    sys.exit(main())
