import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout

# Load datasets
data = pd.read_csv('train.csv')
data1 = pd.read_csv('dataset.csv')
data1 = data1[['text', 'sentiment']]
data = data[['text', 'sentiment']]

# Combine both datasets
data = pd.concat([data, data1], ignore_index=True)

# Drop missing values
data.dropna(inplace=True)

# Encode sentiment labels
sentiment_map = {'negative': 0, 'neutral': 1, 'positive': 2}
data['sentiment'] = data['sentiment'].map(sentiment_map)

# Prepare texts and labels
texts = data['text'].astype(str).tolist()
labels = data['sentiment'].astype(int).tolist()

# Tokenization
max_words = 2000
max_len = 100
tokenizer = Tokenizer(num_words=max_words, lower=True, oov_token="<OOV>")
tokenizer.fit_on_texts(texts)
sequences = tokenizer.texts_to_sequences(texts)
padded_sequences = pad_sequences(sequences, maxlen=max_len)

# Save the tokenizer
with open('tokenizer.pickle_', 'wb') as handle:
    pickle.dump(tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    padded_sequences, labels, test_size=0.2, random_state=42
)

# Convert to numpy arrays
y_train = np.array(y_train)
y_test = np.array(y_test)

# Build the model
model = Sequential()
model.add(Embedding(max_words, 64, input_length=max_len))
model.add(LSTM(64, dropout=0.2, recurrent_dropout=0.2))
model.add(Dense(32, activation='relu'))
model.add(Dropout(0.3))
model.add(Dense(3, activation='softmax'))  # 3 sentiment classes

# Compile model
model.compile(loss='sparse_categorical_crossentropy',
              optimizer='adam', metrics=['accuracy'])

# Train the model and capture history
history = model.fit(X_train, y_train, epochs=10, validation_data=(X_test, y_test))

# Save the trained model
model.save("sentiment_model_.h5")

# Generate PDF report
pdf_path = "training_report.pdf"
with PdfPages(pdf_path) as pdf:
    # Plot Accuracy
    plt.figure(figsize=(8, 6))
    plt.plot(history.history['accuracy'], label='Training Accuracy')
    plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
    plt.title('Model Accuracy')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()
    pdf.savefig()
    plt.close()

    # Plot Loss
    plt.figure(figsize=(8, 6))
    plt.plot(history.history['loss'], label='Training Loss')
    plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.title('Model Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    pdf.savefig()
    plt.close()

    # Write summary text
    summary_text = f"""
    Sentiment Analysis Model Training Report

    - Total Samples: {len(data)}
    - Training Samples: {len(X_train)}
    - Test Samples: {len(X_test)}
    - Vocabulary Size: {max_words}
    - Max Sequence Length: {max_len}
    - Epochs: 10

    Final Training Accuracy: {history.history['accuracy'][-1]:.4f}
    Final Validation Accuracy: {history.history['val_accuracy'][-1]:.4f}
    Final Training Loss: {history.history['loss'][-1]:.4f}
    Final Validation Loss: {history.history['val_loss'][-1]:.4f}
    """

    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis('off')
    ax.text(0, 1, summary_text, verticalalignment='top', fontsize=12, family='monospace')
    pdf.savefig(fig)
    plt.close()

print("✅ Model, tokenizer, and training report PDF saved successfully.")
