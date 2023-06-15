from transformers import RobertaTokenizer, RobertaModel, DistilBertModel, DistilBertTokenizer
from data_processing import DataPreprocessor, tokenize_function, create_dataloaders, DFProcessor, format_time
from sklearn.model_selection import train_test_split
import torch.nn as nn
#from preprocessing import preprocessing_pipeline
import pandas as pd
import nltk
import torch
import numpy as np
from transformers import AdamW, get_linear_schedule_with_warmup
from tqdm import tqdm
import time
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, Normalizer

def train(model, optimizer, loss_function, epochs,       
            train_dataloader, device, clip_value=2):
        train_loss, test_r2 = [], []
        for epoch in range(epochs):
            print("")
            print('======== Epoch {:} / {:} ========'.format(epoch + 1, epochs))
            print('Training...')
            best_loss = 1e10
            total_train_loss = 0
            t0 = time.time()
            model.train()
            for step, batch in enumerate(tqdm(train_dataloader)): 
                batch_inputs, batch_masks, batch_labels = \
                                tuple(b.to(device) for b in batch)
                model.zero_grad()
                outputs = model(batch_inputs, batch_masks)           
                loss = loss_function(outputs.float(), 
                                batch_labels.float())
                total_train_loss+=loss.item()
                loss.backward()
                #clip_grad_norm(model.parameters(), clip_value)
                optimizer.step()
            avg_train_loss = total_train_loss / len(train_dataloader)
            training_time = format_time(time.time() - t0)
            print("")
            print(f"  Average training loss: {avg_train_loss}")
            print("  Training epoch took: {:}".format(training_time))
            train_loss.append(avg_train_loss)

        return model, train_loss

class RobertaRegressor(nn.Module):
    def __init__(self, dropout=0.2, model_name = 'roberta-base'):
        super(RobertaRegressor, self).__init__()
        D_in, D_out = 768, 1
        self.roberta = RobertaModel.from_pretrained(model_name)
        self.regressor = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(D_in, D_out))
        
    def forward(self, input_ids, attention_masks):
        outputs = self.roberta(input_ids, attention_masks)
        class_label_output = outputs[1]
        outputs = self.regressor(class_label_output)
        return outputs
    
if __name__=="__main__":
    # nltk.download('averaged_perceptron_tagger')
    # nltk.download('stopwords')
    # nltk.download('punkt')
    # nltk.download('wordnet')
    # nltk.download()
    # nltk.download('wordnet')
    # print(nltk.find('corpora/wordnet.zip'))
    model_name = 'roberta-base'

    tokenizer = RobertaTokenizer.from_pretrained(model_name)
    #model = RobertaModel.from_pretrained(model_name)

    text_cleaner = DataPreprocessor()
    file = 'ruddit_with_text.csv' 
    df_processor = DFProcessor(filename=file)

    new_df = df_processor.process_df(text_cleaner)
    #tokenizer(examples["clean_text"], padding="max_length", truncation=True)

    encoded_corpus = tokenizer(text = new_df.clean_text.to_list(),
                            add_special_tokens=True,
                            padding='max_length',
                            truncation='longest_first',
                            return_attention_mask=True)
    print(tokenizer.decode(encoded_corpus["input_ids"][0]))

    input_ids = encoded_corpus['input_ids']
    attention_mask = encoded_corpus['attention_mask']
    input_ids = np.array(input_ids)
    attention_mask = np.array(attention_mask)
    labels = new_df.offensiveness_score.to_numpy()

    test_size = 0.1
    batch_size = 8
    ## WILL SPLIT IT UP IN SEPARATE FILES DONT WORRY
    ##
    ##
    train_inputs, test_inputs, train_labels, test_labels = \
            train_test_split(input_ids, labels, test_size=test_size)
    train_masks, test_masks, _, _ = train_test_split(attention_mask, 
                                            labels, test_size=test_size)
    
    train_dataloader = create_dataloaders(train_inputs, train_masks, 
                                        train_labels, batch_size)
    test_dataloader = create_dataloaders(test_inputs, test_masks, 
                                        test_labels, batch_size)
    

    model = RobertaRegressor(dropout=0.2)
    torch.cuda.empty_cache()

    if torch.cuda.is_available():       
        device = torch.device("cuda")
        print("Using GPU.")
    else:
        print("No GPU available, using the CPU instead.")
        device = torch.device("cpu")
    model.to(device)
    
    optimizer = AdamW(model.parameters(),
                  lr=5e-4,
                  eps=1e-8)
    epochs = 50
    total_steps = len(train_dataloader) * epochs
    # scheduler = get_linear_schedule_with_warmup(optimizer,       
    #                 num_warmup_steps=0, num_training_steps=total_steps)
    scheduler = get_linear_schedule_with_warmup(optimizer,       
                 num_warmup_steps=0, num_training_steps=total_steps)
    loss_function = nn.MSELoss()

    from torch.nn.utils.clip_grad import clip_grad_norm
    model, train_loss = train(model, optimizer, loss_function, epochs, 
                train_dataloader, device)
    torch.save(model.state_dict() ,f"saved_models/{model_name}_{epochs}.pt")
    plt.plot(train_loss, 'b-o', label="Training")
    plt.show()