python main.py \
    --do_predict \
    --model_name_or_path=IreneXu/MuseCoco_text2attribute \
    --test_file=data/predict.json \
    --attributes=data/att_key.json \
    --num_labels=num_labels.json \
    --output_dir=./tmp \
    --overwrite_output_dir