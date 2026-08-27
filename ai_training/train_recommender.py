import torch
import torch.nn as nn
import torchvision.models as models
import os

class FashionCompatibilityModel(nn.Module):
    def __init__(self, embedding_dim=512):
        super(FashionCompatibilityModel, self).__init__()
        # Load a pretrained ResNet50 as feature extractor
        resnet = models.resnet50(pretrained=True)
        # Remove the final classification layer
        self.feature_extractor = nn.Sequential(*list(resnet.children())[:-1])
        # Add a projection head to embedding space
        self.projection = nn.Linear(resnet.fc.in_features, embedding_dim)

    def forward(self, x):
        features = self.feature_extractor(x)
        features = features.view(features.size(0), -1)
        embeddings = self.projection(features)
        # Normalize embeddings (useful for cosine similarity / FAISS)
        return nn.functional.normalize(embeddings, p=2, dim=1)

def train_model():
    print("=== Khởi tạo Fashion Compatibility Model (Siamese Network) ===")
    model = FashionCompatibilityModel()
    
    # 1. TODO: Dataset - Load DeepFashion hoặc Polyvore dataset ở đây
    # train_loader = DataLoader(FashionDataset(...), batch_size=32, shuffle=True)
    
    # 2. TODO: Loss Function - Khuyên dùng TripletMarginLoss hoặc ContrastiveLoss
    # criterion = nn.TripletMarginLoss(margin=1.0)
    
    # 3. TODO: Optimizer
    # optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    print("[MÔ PHỎNG] Bắt đầu quá trình Training (Epoch 1/10)...")
    print("[MÔ PHỎNG] Training hoàn tất.")
    
    # Lưu model (.pt) để Backend FastAPI tải lên
    os.makedirs("models", exist_ok=True)
    torch.save(model.state_dict(), "models/fashion_recommender.pt")
    print("Đã lưu model vào thư mục 'models/fashion_recommender.pt'")

if __name__ == "__main__":
    print("Boilerplate Train AI cho Đồ án (Khuyên dùng: Upload file này lên Google Colab để train với GPU)")
    train_model()
