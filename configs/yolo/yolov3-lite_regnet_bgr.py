######################################################
input_size = (416,416)                          #(320,320) #(416,416) #(608,608)
dataset_type = 'CocoDataset'
num_classes_dict = {'CocoDataset':80, 'VOCDataset':20, 'CityscapesDataset':8}
num_classes = num_classes_dict[dataset_type]
img_norm_cfg = dict(mean=[103.53, 116.28, 123.675], std=[57.375, 57.12, 58.395], to_rgb=False) #imagenet mean used in pycls (bgr)

_base_ = [
    f'../_xbase_/datasets/{dataset_type.lower()}.py',
    '../_xbase_/hyper_params/common_config.py',
    '../_xbase_/hyper_params/yolo_config.py',
    '../_xbase_/hyper_params/schedule.py',
]

######################################################
# settings for qat or calibration - uncomment after doing floating point training
# also change dataset_repeats in the dataset config to 1 for fast learning
quantize = False #'training' #'calibration'
initial_learning_rate = 8e-2
samples_per_gpu = 16
if quantize:
  load_from = './work_dirs/yolov3-lite_regnet/latest.pth'
  optimizer = dict(type='SGD', lr=initial_learning_rate/1000.0, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
  total_epochs = 1 if quantize == 'calibration' else 12
else:
  optimizer = dict(type='SGD', lr=initial_learning_rate, momentum=0.9, weight_decay=4e-5) #1e-4 => 4e-5
#

######################################################
backbone_type = 'RegNet'
backbone_arch = 'regnetx_1.6gf'                  # 'regnetx_800mf' #'regnetx_1.6gf' #'regnetx_3.2gf'
to_rgb = False                                   # pycls regnet backbones are trained with bgr

decoder_fpn_type = 'FPNLite'                    # 'FPNLite' #'BiFPNLite' #'FPN'
decoder_conv_type = 'ConvDWSep'                 # 'ConvDWSep' #'ConvDWTripletRes' #'ConvDWTripletAlwaysRes'
fpn_width_fact = 2 if decoder_fpn_type == 'BiFPNLite' else 4
decoder_width_fact = 2 if decoder_fpn_type == 'BiFPNLite' else 4
decoder_depth_fact = 4

regnet_settings = {
    'regnetx_200mf': {'bacbone_out_channels': [32, 56, 152, 368], 'group_size_dw': 8,
                      'fpn_intermediate_channels': min(28*fpn_width_fact,256),
                      'fpn_out_channels': min(28*decoder_width_fact,256),
                      'fpn_num_blocks': decoder_depth_fact,
                      'pretrained': './checkpoints/RegNetX-200MF_dds_8gpu_mmdet-converted.pyth'},
    'regnetx_400mf': {'bacbone_out_channels': [32, 64, 160, 384], 'group_size_dw': 16,
                      'fpn_intermediate_channels': min(32*fpn_width_fact,256),
                      'fpn_out_channels': min(32*decoder_width_fact,256),
                      'fpn_num_blocks': decoder_depth_fact,
                      'pretrained': 'open-mmlab://regnetx_400mf'},
    'regnetx_800mf':{'bacbone_out_channels':[64, 128, 288, 672], 'group_size_dw':16,
                     'fpn_intermediate_channels':min(64*fpn_width_fact,256),
                     'fpn_out_channels':min(64*decoder_width_fact,256),
                     'fpn_num_blocks':decoder_depth_fact,
                     'pretrained':'open-mmlab://regnetx_800mf'},
    'regnetx_1.6gf':{'bacbone_out_channels':[72, 168, 408, 912], 'group_size_dw':24,
                     'fpn_intermediate_channels':min(84*fpn_width_fact,264),
                     'fpn_out_channels':min(84*decoder_width_fact,264),
                     'fpn_num_blocks':decoder_depth_fact,
                     'pretrained':'open-mmlab://regnetx_1.6gf'},
    'regnetx_3.2gf':{'bacbone_out_channels':[96, 192, 432, 1008], 'group_size_dw':48,
                     'fpn_intermediate_channels':min(96*fpn_width_fact,288),
                     'fpn_out_channels':min(96*decoder_width_fact,288),
                     'fpn_num_blocks':decoder_depth_fact,
                     'pretrained': 'open-mmlab://regnetx_3.2gf'}
}

######################################################
regnet_cfg = regnet_settings[backbone_arch]
pretrained=regnet_cfg['pretrained']
bacbone_out_channels=regnet_cfg['bacbone_out_channels']
backbone_out_indices = (0, 1, 2, 3)


input_size_divisor = 32
conv_cfg = dict(type='ConvDWSep', group_size_dw=16)
norm_cfg = dict(type='BN')
act_cfg=dict(type='ReLU')

model = dict(
    type='YOLOV3',
    pretrained=pretrained,
    backbone=dict(
        type=backbone_type,
        arch=backbone_arch,
        out_indices=backbone_out_indices,
        norm_eval=False,
        style='pytorch'),
    neck=dict(
        type='YOLOV3LiteNeck',
        num_scales=3,
        in_channels=bacbone_out_channels[-3:][::-1],
        out_channels=[512, 256, 128],
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        act_cfg=act_cfg),
    bbox_head=dict(
        type='YOLOV3LiteHead',
        num_classes=80,
        in_channels=[512, 256, 128],
        out_channels=[1024, 512, 256],
        conv_cfg=conv_cfg,
        norm_cfg=norm_cfg,
        act_cfg=act_cfg,
        anchor_generator=dict(
            type='YOLOAnchorGenerator',
            base_sizes=[[(116, 90), (156, 198), (373, 326)],
                        [(30, 61), (62, 45), (59, 119)],
                        [(10, 13), (16, 30), (33, 23)]],
            strides=[32, 16, 8]),
        bbox_coder=dict(type='YOLOBBoxCoder'),
        featmap_strides=[32, 16, 8],
        loss_cls=dict(
            type='CrossEntropyLoss',
            use_sigmoid=True,
            loss_weight=1.0,
            reduction='sum'),
        loss_conf=dict(
            type='CrossEntropyLoss',
            use_sigmoid=True,
            loss_weight=1.0,
            reduction='sum'),
        loss_xy=dict(
            type='CrossEntropyLoss',
            use_sigmoid=True,
            loss_weight=2.0,
            reduction='sum'),
        loss_wh=dict(type='MSELoss', loss_weight=2.0, reduction='sum')))

# dataset settings
train_pipeline = [
    dict(type='LoadImageFromFile', to_float32=True),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(type='PhotoMetricDistortion') if not quantize else dict(type='Bypass'),
    dict(
        type='Expand',
        mean=img_norm_cfg['mean'],
        to_rgb=img_norm_cfg['to_rgb'],
        ratio_range=(1, 2)),
    dict(
        type='MinIoURandomCrop',
        min_ious=(0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
        min_crop_size=0.3),
    dict(type='Resize', img_scale=input_size, keep_ratio=False),
    dict(type='RandomFlip', flip_ratio=0.5),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='Pad', size_divisor=input_size_divisor),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels'])
]

test_pipeline = [
    dict(type='LoadImageFromFile'),
    dict(
        type='MultiScaleFlipAug',
        img_scale=input_size,
        flip=False,
        transforms=[
            dict(type='Resize', keep_ratio=False),
            dict(type='RandomFlip'),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='Pad', size_divisor=input_size_divisor),
            dict(type='ImageToTensor', keys=['img']),
            dict(type='Collect', keys=['img']),
        ])
]

data = dict(
    samples_per_gpu=samples_per_gpu,
    workers_per_gpu=0,
    train=dict(dataset=dict(pipeline=train_pipeline)),
    val=dict(pipeline=test_pipeline),
    test=dict(pipeline=test_pipeline))
