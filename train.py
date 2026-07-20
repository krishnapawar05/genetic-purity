"""
AI-Assisted Genetic Purity Prediction Using Morphological Features of Germinated Plants.
Production-ready training and evaluation pipeline for image classification.
"""

import os
import tensorflow as tf
import time
import sys
import logging
import csv
import platform
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
# pyrefly: ignore [missing-import]
from tensorflow.keras.applications.mobilenet import preprocess_input, MobileNet
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_recall_fscore_support
)

# ==============================================================================
# CENTRALIZED CONFIGURATION SECTION
# ==============================================================================
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
EPOCHS = 10
LEARNING_RATE = 0.001
RANDOM_SEED = 42
MODEL_SAVE_PATH = "model.keras"
RESULTS_DIR = "results"
# ==============================================================================

# Set random seeds for reproducibility
tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Global logger placeholder
logger = None


def setup_directories_and_logging():
    """
    Creates results and model output directories, and initializes
    the logging configuration to output to both console and training.log.
    """
    global logger
    
    # 1. Create directories
    os.makedirs(RESULTS_DIR, exist_ok=True)
    model_dir = os.path.dirname(MODEL_SAVE_PATH)
    if model_dir:
        os.makedirs(model_dir, exist_ok=True)
        
    # 2. Configure logging
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_file_path = os.path.join(RESULTS_DIR, "training.log")
    
    # Reset existing logging configurations to prevent duplicate logs
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("genetic_purity_pipeline")


def get_system_info():
    """
    Collects and returns information about Python, TensorFlow, and hardware devices.
    """
    py_version = sys.version.replace('\n', ' ')
    tf_version = tf.__version__
    
    # Check GPU and CPU hardware availability
    gpus = tf.config.list_physical_devices('GPU')
    cpus = tf.config.list_physical_devices('CPU')
    
    gpu_info = f"GPUs detected: {len(gpus)}"
    if gpus:
        for idx, gpu in enumerate(gpus):
            gpu_info += f"\n  - GPU {idx}: {gpu}"
    else:
        gpu_info += " (No GPU available, running on CPU)"
        
    cpu_info = f"CPUs detected: {len(cpus)}"
    
    sys_info = (
        f"Python Version:      {py_version}\n"
        f"TensorFlow Version:  {tf_version}\n"
        f"OS Platform:         {platform.platform()}\n"
        f"System Architecture: {platform.machine()}\n"
        f"Device Info:\n"
        f"  * {cpu_info}\n"
        f"  * {gpu_info}"
    )
    return sys_info


def count_images_in_dir(path):
    """
    Optimized helper function to count image files in a directory.
    
    Args:
        path (str): Target directory path.
        
    Returns:
        int: Number of files with valid image extensions.
    """
    valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
    if not os.path.exists(path):
        return 0
    try:
        count = 0
        for entry in os.scandir(path):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in valid_exts:
                count += 1
        return count
    except Exception:
        return 0


def generate_dataset_summary(train_dir, test_dir, required_classes):
    """
    Calculates statistics on the training and testing datasets.
    
    Args:
        train_dir (str): Path to training directory.
        test_dir (str): Path to testing directory.
        required_classes (list): List of expected class directories.
        
    Returns:
        str: Formatted string summarizing the dataset metrics.
    """
    train_counts = {}
    test_counts = {}
    total_train = 0
    total_test = 0
    
    for cls in required_classes:
        tr_c = count_images_in_dir(os.path.join(train_dir, cls))
        te_c = count_images_in_dir(os.path.join(test_dir, cls))
        train_counts[cls] = tr_c
        test_counts[cls] = te_c
        total_train += tr_c
        total_test += te_c
        
    summary = (
        f"Number of classes: {len(required_classes)}\n"
        f"Class names:       {required_classes}\n\n"
        f"Training Dataset:\n"
        f"  Total Images:    {total_train}\n"
    )
    for cls, count in train_counts.items():
        summary += f"    - {cls}: {count} images\n"
        
    summary += f"\nTesting Dataset:\n"
    summary += f"  Total Images:    {total_test}\n"
    for cls, count in test_counts.items():
        summary += f"    - {cls}: {count} images\n"
        
    return summary


def load_dataset(data_dir, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE, shuffle=True):
    """
    Loads images from the specified directory using Keras' utility.
    
    Args:
        data_dir (str): Path to the target directory.
        image_size (tuple): Target dimensions for resizing the images.
        batch_size (int): Size of batches of data.
        shuffle (bool): Whether to shuffle the data.
        
    Returns:
        tuple: (dataset as tf.data.Dataset, list of class names)
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"The directory '{data_dir}' does not exist.")
    
    # Load with label_mode='categorical' as loss is Categorical Crossentropy
    dataset = tf.keras.utils.image_dataset_from_directory(
        data_dir,
        image_size=image_size,
        batch_size=batch_size,
        label_mode='categorical',
        shuffle=shuffle
    )
    return dataset, dataset.class_names


def preprocess_dataset(dataset, is_training=True):
    """
    Preprocesses and optimizes the tf.data.Dataset pipeline.
    
    Data Leakage Prevention:
    - Data augmentation is applied strictly to the training dataset.
    - Testing dataset is only processed with deterministic preprocessing.
    
    Pipeline Optimization:
    - cache(): Caches the dataset in memory after initial read/preprocessing.
    - prefetch(): Prepares batches in the background using tf.data.AUTOTUNE.
    
    Args:
        dataset (tf.data.Dataset): The raw input dataset.
        is_training (bool): Flag indicating if this is the training dataset.
        
    Returns:
        tf.data.Dataset: The preprocessed and optimized dataset.
    """
    try:
        if is_training:
            # Data augmentation sequential block applied only on the training set
            data_augmentation = tf.keras.Sequential([
                tf.keras.layers.RandomRotation(factor=0.2),
                tf.keras.layers.RandomFlip(mode="horizontal"),
                tf.keras.layers.RandomZoom(height_factor=0.2, width_factor=0.2),
                tf.keras.layers.RandomBrightness(factor=0.2, value_range=(0.0, 255.0))
            ], name="data_augmentation")
            
            # Map data augmentation
            dataset = dataset.map(
                lambda x, y: (data_augmentation(x, training=True), y),
                num_parallel_calls=tf.data.AUTOTUNE
            )
            
        # Apply MobileNet specific preprocess_input (scales inputs from [0, 255] to [-1, 1])
        dataset = dataset.map(
            lambda x, y: (preprocess_input(x), y),
            num_parallel_calls=tf.data.AUTOTUNE
        )
        
        # Cache the dataset to speed up subsequent epochs
        dataset = dataset.cache()
        
        # Prefetch batches to optimize GPU/CPU execution overlap
        dataset = dataset.prefetch(buffer_size=tf.data.AUTOTUNE)
        
        return dataset
        
    except Exception as e:
        logger.error(f"Error during dataset preprocessing: {str(e)}")
        raise


def build_model(input_shape=(224, 224, 3), num_classes=3, learning_rate=LEARNING_RATE):
    """
    Constructs the transfer learning model based on MobileNet.
    
    Architecture:
    - MobileNet backbone pre-trained on ImageNet (frozen).
    - GlobalAveragePooling2D layer.
    - Dense hidden layer with 256 units and ReLU activation.
    - Dropout layer with 50% rate.
    - Output Dense layer with Softmax activation for 3 classes.
    
    Args:
        input_shape (tuple): Shape of the input images.
        num_classes (int): Number of target classification classes.
        learning_rate (float): Learning rate for the Adam optimizer.
        
    Returns:
        tf.keras.Model: Compiled Keras model.
    """
    try:
        # Load original MobileNet with ImageNet pretrained weights, excluding classification head
        base_model = MobileNet(
            input_shape=input_shape,
            include_top=False,
            weights='imagenet'
        )
        
        # Freeze pretrained backbone to prevent modifying learned weights
        base_model.trainable = False
        
        # Construct the classification model
        model = tf.keras.Sequential([
            base_model,
            tf.keras.layers.GlobalAveragePooling2D(),
            tf.keras.layers.Dense(256, activation='relu', name='dense_hidden_relu'),
            tf.keras.layers.Dropout(0.5, name='dropout_layer'),
            tf.keras.layers.Dense(num_classes, activation='softmax', name='output_softmax')
        ], name="MobileNet_Genetic_Purity_Classifier")
        
        # Compile model using configurations:
        # Optimizer: Adam, Loss: Categorical Crossentropy, Metric: Accuracy
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
            loss=tf.keras.losses.CategoricalCrossentropy(),
            metrics=['accuracy']
        )
        
        return model
        
    except Exception as e:
        logger.error(f"Error during model building: {str(e)}")
        raise


def train_model(model, train_ds, val_ds, epochs=EPOCHS):
    """
    Fits the model on the training dataset while validating on the validation dataset.
    
    Args:
        model (tf.keras.Model): The compiled Keras model.
        train_ds (tf.data.Dataset): The training dataset.
        val_ds (tf.data.Dataset): The validation/testing dataset.
        epochs (int): Number of epochs.
        
    Returns:
        tf.keras.callbacks.History: Training history object.
    """
    try:
        # Train model with progress displayed
        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
            verbose=1
        )
        return history
    except Exception as e:
        logger.error(f"Error during model training: {str(e)}")
        raise


def evaluate_model(model, test_ds, class_names):
    """
    Evaluates the model and computes essential performance metrics.
    
    Args:
        model (tf.keras.Model): The trained Keras model.
        test_ds (tf.data.Dataset): Preprocessed testing dataset (shuffling=False).
        class_names (list): List of class labels.
        
    Returns:
        dict: Containing accuracy, precision, recall, f1_score, confusion matrix, 
              classification report, y_true, and y_pred.
    """
    try:
        logger.info("Executing evaluation predictions on the test dataset...")
        y_pred_probs = model.predict(test_ds, verbose=1)
        y_pred = np.argmax(y_pred_probs, axis=1)
        
        # Extract original target labels
        y_true_list = []
        for _, labels in test_ds:
            y_true_list.append(labels.numpy())
        y_true_onehot = np.concatenate(y_true_list, axis=0)
        y_true = np.argmax(y_true_onehot, axis=1)
        
        # Calculate metric values
        accuracy = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro')
        
        cm = confusion_matrix(y_true, y_pred)
        report = classification_report(y_true, y_pred, target_names=class_names)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'confusion_matrix': cm,
            'classification_report': report,
            'y_true': y_true,
            'y_pred': y_pred
        }
        
    except Exception as e:
        logger.error(f"Error during model evaluation: {str(e)}")
        raise


def plot_training_history(history, output_dir=RESULTS_DIR):
    """
    Generates and saves individual graphs for loss and accuracy metrics.
    
    Args:
        history (tf.keras.callbacks.History): Training history.
        output_dir (str): Directory where the plots will be saved.
    """
    try:
        epochs = range(1, len(history.history['accuracy']) + 1)
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Training Accuracy Graph
        plt.figure(figsize=(8, 6))
        plt.plot(epochs, history.history['accuracy'], 'b-o', linewidth=2, label='Training Accuracy')
        plt.title('Training Accuracy Graph')
        plt.xlabel('Epochs')
        plt.ylabel('Accuracy')
        plt.legend(loc='lower right')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'training_accuracy.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Validation Accuracy Graph
        plt.figure(figsize=(8, 6))
        if 'val_accuracy' in history.history:
            plt.plot(epochs, history.history['val_accuracy'], 'r-o', linewidth=2, label='Validation Accuracy')
        plt.title('Validation Accuracy Graph')
        plt.xlabel('Epochs')
        plt.ylabel('Accuracy')
        plt.legend(loc='lower right')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'validation_accuracy.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Training Loss Graph
        plt.figure(figsize=(8, 6))
        plt.plot(epochs, history.history['loss'], 'b-o', linewidth=2, label='Training Loss')
        plt.title('Training Loss Graph')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.legend(loc='upper right')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'training_loss.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. Validation Loss Graph
        plt.figure(figsize=(8, 6))
        if 'val_loss' in history.history:
            plt.plot(epochs, history.history['val_loss'], 'r-o', linewidth=2, label='Validation Loss')
        plt.title('Validation Loss Graph')
        plt.xlabel('Epochs')
        plt.ylabel('Loss')
        plt.legend(loc='upper right')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'validation_loss.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
    except Exception as e:
        logger.error(f"Error during training history plotting: {str(e)}")
        raise


def save_training_history_csv(history, filepath):
    """
    Saves the training history to a CSV file.
    
    Args:
        history (tf.keras.callbacks.History): Training history.
        filepath (str): Path of the destination CSV file.
    """
    try:
        acc = history.history['accuracy']
        val_acc = history.history.get('val_accuracy', [None] * len(acc))
        loss = history.history['loss']
        val_loss = history.history.get('val_loss', [None] * len(acc))
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Epoch', 'Training Accuracy', 'Validation Accuracy', 'Training Loss', 'Validation Loss'])
            for i in range(len(acc)):
                writer.writerow([i + 1, acc[i], val_acc[i], loss[i], val_loss[i]])
    except Exception as e:
        logger.error(f"Error saving training history CSV: {str(e)}")
        raise


def save_results(metrics, output_dir=RESULTS_DIR, class_names=None):
    """
    Saves the Classification Report (.txt) and Confusion Matrix (.png) to results directory.
    
    Args:
        metrics (dict): Dict of calculated metrics from evaluate_model().
        output_dir (str): Directory where the results will be saved.
        class_names (list): List of class labels.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        # Save Classification Report (.txt)
        report_path = os.path.join(output_dir, 'classification_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("AI-ASSISTED GENETIC PURITY PREDICTION - CLASSIFICATION REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Global Accuracy: {metrics['accuracy']:.4f}\n")
            f.write(f"Macro Precision: {metrics['precision']:.4f}\n")
            f.write(f"Macro Recall:    {metrics['recall']:.4f}\n")
            f.write(f"Macro F1 Score:  {metrics['f1_score']:.4f}\n\n")
            f.write(metrics['classification_report'])
        
        # Save Confusion Matrix (.png)
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            metrics['confusion_matrix'],
            annot=True,
            fmt='d',
            cmap='Blues',
            xticklabels=class_names,
            yticklabels=class_names,
            cbar=True
        )
        plt.title('Confusion Matrix')
        plt.ylabel('True Class')
        plt.xlabel('Predicted Class')
        plt.savefig(os.path.join(output_dir, 'confusion_matrix.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
    except Exception as e:
        logger.error(f"Error during saving results: {str(e)}")
        raise


def save_model(model, filepath=MODEL_SAVE_PATH):
    """
    Saves the trained model to disk in .keras format.
    
    Args:
        model (tf.keras.Model): The trained model.
        filepath (str): Path where the model will be stored.
    """
    try:
        model.save(filepath)
        logger.info(f"Trained model successfully saved to: {filepath}")
    except Exception as e:
        logger.error(f"Error saving model: {str(e)}")
        raise


def main():
    # Measure execution time
    start_time = time.time()
    
    try:
        # Step 1: Set up directories and logging configuration
        setup_directories_and_logging()
        
        logger.info("============================================================")
        logger.info("AI-Assisted Genetic Purity Prediction Pipeline Started")
        logger.info("============================================================")
        
        # Step 2: Display and save system information
        logger.info("Step 1: Retrieving System Hardware & Software Info...")
        sys_info = get_system_info()
        logger.info(f"\n{sys_info}\n")
        
        # Save system info
        sys_info_path = os.path.join(RESULTS_DIR, "system_info.txt")
        with open(sys_info_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("SYSTEM AND ENVIRONMENT INFORMATION\n")
            f.write("=" * 60 + "\n")
            f.write(sys_info + "\n")
        logger.info(f"System info saved to: {sys_info_path}")
        
        # Step 3: Set and validate directories
        logger.info("Step 2: Locating and Validating Dataset Directories...")
        train_dir = r"C:\Users\Krishna Pawar\Downloads\New\plant-genetic-prediction\dataset\train"
        test_dir = r"C:\Users\Krishna Pawar\Downloads\New\plant-genetic-prediction\dataset\test"
            
        # Dataset validation
        if not os.path.exists(train_dir):
            raise FileNotFoundError(f"Training dataset directory not found at: {train_dir}")
        if not os.path.exists(test_dir):
            raise FileNotFoundError(f"Testing dataset directory not found at: {test_dir}")
            
        # Validate that class folders exist
        required_classes = ['male', 'female', 'hybrid']
        for cls in required_classes:
            train_cls_dir = os.path.join(train_dir, cls)
            test_cls_dir = os.path.join(test_dir, cls)
            if not os.path.exists(train_cls_dir):
                raise FileNotFoundError(f"Required training class subdirectory missing: {train_cls_dir}")
            if not os.path.exists(test_cls_dir):
                raise FileNotFoundError(f"Required testing class subdirectory missing: {test_cls_dir}")
        
        logger.info(f"Training Directory: {train_dir}")
        logger.info(f"Testing Directory:  {test_dir}")
        
        # Step 4: Generate Dataset Summary
        logger.info("Step 3: Calculating Dataset Statistics...")
        dataset_summary = generate_dataset_summary(train_dir, test_dir, required_classes)
        logger.info(f"\n{dataset_summary}")
        
        # Save dataset summary to text file
        dataset_summary_path = os.path.join(RESULTS_DIR, "dataset_summary.txt")
        with open(dataset_summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("DATASET STATISTICS AND SUMMARY\n")
            f.write("=" * 60 + "\n")
            f.write(dataset_summary + "\n")
        logger.info(f"Dataset summary saved to: {dataset_summary_path}")
        
        # Step 5: Load raw dataset
        logger.info("Step 4: Loading Dataset using image_dataset_from_directory...")
        # Shuffle=True for train, shuffle=False for test to maintain class order alignment
        train_ds_raw, class_names = load_dataset(train_dir, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE, shuffle=True)
        test_ds_raw, test_class_names = load_dataset(test_dir, image_size=IMAGE_SIZE, batch_size=BATCH_SIZE, shuffle=False)
        
        # Class validation
        logger.info(f"Detected class labels: {class_names}")
        assert set(class_names) == set(required_classes), f"Class directory mismatch. Found {class_names}, expected {required_classes}"
        assert class_names == test_class_names, f"Class ordering mismatch between train and test datasets."
        
        # Save class mapping
        classes_path = os.path.join(RESULTS_DIR, "classes.txt")
        with open(classes_path, 'w', encoding='utf-8') as f:
            for idx, name in enumerate(class_names):
                f.write(f"{idx}: {name}\n")
        logger.info(f"Class mapping successfully saved to: {classes_path}")
        
        # Dataset batch statistics
        train_batches = tf.data.experimental.cardinality(train_ds_raw).numpy()
        test_batches = tf.data.experimental.cardinality(test_ds_raw).numpy()
        logger.info(f"Training set loaded: {train_batches} batches of size {BATCH_SIZE}.")
        logger.info(f"Testing set loaded: {test_batches} batches of size {BATCH_SIZE}.")
        
        # Step 6: Preprocess and optimize dataset
        logger.info("Step 5: Preprocessing Datasets & Implementing Performance Optimizations...")
        train_ds = preprocess_dataset(train_ds_raw, is_training=True)
        test_ds = preprocess_dataset(test_ds_raw, is_training=False)
        
        # Step 7: Model creation
        logger.info("Step 6: Constructing Model with MobileNet Backbone...")
        model = build_model(input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3), num_classes=len(class_names), learning_rate=LEARNING_RATE)
        
        # Print summary in console
        model.summary()
        
        # Save model summary to text file
        summary_path = os.path.join(RESULTS_DIR, 'model_summary.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            model.summary(print_fn=lambda x: f.write(x + '\n'))
        logger.info(f"Model architecture summary saved to: {summary_path}")
        
        # Step 8: Train model
        logger.info("Step 7: Beginning Model Training (epochs=10)...")
        train_start = time.time()
        history = train_model(model, train_ds, test_ds, epochs=EPOCHS)
        train_end = time.time()
        total_training_time = train_end - train_start
        logger.info(f"Model training finished in {total_training_time:.2f} seconds.")
        
        # Step 9: Save complete training history to CSV
        history_csv_path = os.path.join(RESULTS_DIR, "training_history.csv")
        save_training_history_csv(history, history_csv_path)
        logger.info(f"Training history saved to: {history_csv_path}")
        
        # Step 10: Model evaluation
        logger.info("Step 8: Beginning Model Evaluation...")
        metrics = evaluate_model(model, test_ds, class_names)
        
        # Compute test loss
        test_loss, _ = model.evaluate(test_ds, verbose=0)
        metrics['loss'] = test_loss
        
        # Print metrics summary to stdout
        logger.info("\n" + "=" * 60)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Accuracy:  {metrics['accuracy']:.4f}")
        logger.info(f"Loss:      {metrics['loss']:.4f}")
        logger.info(f"Precision: {metrics['precision']:.4f}")
        logger.info(f"Recall:    {metrics['recall']:.4f}")
        logger.info(f"F1 Score:  {metrics['f1_score']:.4f}")
        logger.info("\nClassification Report:")
        logger.info("\n" + metrics['classification_report'])
        logger.info("\nConfusion Matrix:")
        logger.info(f"\n{metrics['confusion_matrix']}")
        logger.info("=" * 60)
        
        # Step 11: Save outputs and graphs
        logger.info("Step 9: Generating Graphs, Report, & Metrics Files...")
        save_results(metrics, RESULTS_DIR, class_names)
        plot_training_history(history, RESULTS_DIR)
        
        # Save metrics summary to metrics.txt
        metrics_path = os.path.join(RESULTS_DIR, 'metrics.txt')
        with open(metrics_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("TRAINING AND EVALUATION METRICS SUMMARY\n")
            f.write("=" * 60 + "\n")
            f.write(f"Optimizer:             Adam\n")
            f.write(f"Loss Function:         Categorical Crossentropy\n")
            f.write(f"Learning Rate:         {LEARNING_RATE}\n")
            f.write(f"Batch Size:            {BATCH_SIZE}\n")
            f.write(f"Epochs:                {EPOCHS}\n")
            f.write(f"Total Training Time:   {total_training_time:.2f} seconds\n")
            f.write("-" * 60 + "\n")
            f.write(f"Test Accuracy:         {metrics['accuracy']:.4f}\n")
            f.write(f"Test Loss:             {metrics['loss']:.4f}\n")
            f.write(f"Macro Precision:       {metrics['precision']:.4f}\n")
            f.write(f"Macro Recall:          {metrics['recall']:.4f}\n")
            f.write(f"Macro F1 Score:        {metrics['f1_score']:.4f}\n")
            f.write("=" * 60 + "\n")
        logger.info(f"Metrics summary saved to: {metrics_path}")
        
        # Step 12: Save final trained model
        logger.info("Step 10: Saving Final Model...")
        save_model(model, MODEL_SAVE_PATH)
        
        # Total execution time
        elapsed = time.time() - start_time
        logger.info(f"Execution completed successfully. Total execution time: {elapsed:.2f} seconds.")
        
    except Exception as e:
        if logger:
            logger.critical(f"Critical failure in training pipeline: {str(e)}", exc_info=True)
        else:
            print(f"Critical failure in training pipeline: {str(e)}", file=sys.stderr)
        sys.exit(1)
        
    finally:
        # Step 13: Clean up TensorFlow session
        print("\nCleaning up TensorFlow session...")
        tf.keras.backend.clear_session()


if __name__ == "__main__":
    main()
