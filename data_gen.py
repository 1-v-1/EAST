import os

import cv2 as cv
import numpy as np
from torch.utils.data import Dataset
from torchvision import transforms

from config import input_size, training_data_path, background_ratio, random_scale, geometry
from icdar import load_annoataion, get_images, check_and_validate_polys, crop_area, generate_rbox

# Data augmentation and normalization for training
# Just normalization for validation
data_transforms = {
    'train': transforms.Compose([
        transforms.ColorJitter(0.5, 0.5, 0.5, 0.25),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]),
    'valid': transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
}


class EastDataset(Dataset):
    def __init__(self, split):
        self.split = split

        self.image_list = np.array(get_images())
        print('{} training images in {}'.format(
            self.image_list.shape[0], training_data_path))

        self.transformer = data_transforms[split]

    def __getitem__(self, i):
        im_fn = self.image_list[i]
        im = cv.imread(im_fn)
        # print im_fn
        h, w, _ = im.shape
        txt_fn = im_fn.replace(os.path.basename(im_fn).split('.')[1], 'txt')
        print(txt_fn)
        assert (os.path.exists(txt_fn))

        text_polys, text_tags = load_annoataion(txt_fn)

        text_polys, text_tags = check_and_validate_polys(text_polys, text_tags, (h, w))
        # if text_polys.shape[0] == 0:
        #     continue
        # random scale this image
        rd_scale = np.random.choice(random_scale)
        im = cv.resize(im, dsize=None, fx=rd_scale, fy=rd_scale)
        text_polys *= rd_scale
        # print rd_scale
        # random crop a area from image
        if np.random.rand() < background_ratio:
            # crop background
            im, text_polys, text_tags = crop_area(im, text_polys, text_tags, crop_background=True)
            assert (text_polys.shape[0] > 0)
            # pad and resize image
            new_h, new_w, _ = im.shape
            max_h_w_i = np.max([new_h, new_w, input_size])
            im_padded = np.zeros((max_h_w_i, max_h_w_i, 3), dtype=np.uint8)
            im_padded[:new_h, :new_w, :] = im.copy()
            im = cv.resize(im_padded, dsize=(input_size, input_size))
            score_map = np.zeros((input_size, input_size), dtype=np.uint8)
            geo_map_channels = 5 if geometry == 'RBOX' else 8
            geo_map = np.zeros((input_size, input_size, geo_map_channels), dtype=np.float32)
            training_mask = np.ones((input_size, input_size), dtype=np.uint8)
        else:
            im, text_polys, text_tags = crop_area(im, text_polys, text_tags, crop_background=False)
            assert (text_polys.shape[0] == 0)

            h, w, _ = im.shape

            # pad the image to the training input size or the longer side of image
            new_h, new_w, _ = im.shape
            max_h_w_i = np.max([new_h, new_w, input_size])
            im_padded = np.zeros((max_h_w_i, max_h_w_i, 3), dtype=np.uint8)
            im_padded[:new_h, :new_w, :] = im.copy()
            im = im_padded
            # resize the image to input size
            new_h, new_w, _ = im.shape
            resize_h = input_size
            resize_w = input_size
            im = cv.resize(im, dsize=(resize_w, resize_h))
            resize_ratio_3_x = resize_w / float(new_w)
            resize_ratio_3_y = resize_h / float(new_h)
            text_polys[:, :, 0] *= resize_ratio_3_x
            text_polys[:, :, 1] *= resize_ratio_3_y
            new_h, new_w, _ = im.shape
            score_map, geo_map, training_mask = generate_rbox((new_h, new_w), text_polys, text_tags)

        return im, score_map, geo_map, training_mask

    def __len__(self):
        return len(self.image_list)


if __name__ == "__main__":
    dataset = EastDataset('train')
    print(dataset[0][1])
