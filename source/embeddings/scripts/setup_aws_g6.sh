#!/bin/bash
#
# Setup rápido para AWS G6 instance - Fine-tuning de Embeddings
# Execute: bash setup_aws_g6.sh
#

set -e

echo "================================================================================"
echo "SETUP AWS G6 - FINE-TUNING DE EMBEDDINGS"
echo "================================================================================"
echo ""

# 1. Verificar GPU
echo "📊 Verificando GPU..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  nvidia-smi não encontrado. Instalando drivers NVIDIA..."
    sudo apt update
    sudo apt install -y nvidia-driver-560
    echo "✅ Driver instalado. REINICIE a instância: sudo reboot"
    exit 0
fi

nvidia-smi
echo ""

# 2. Instalar Python 3.11 e pip
echo "🐍 Instalando Python 3.11..."
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
echo "✅ Python instalado"
echo ""

# 3. Criar ambiente virtual
echo "📦 Criando ambiente virtual..."
python3.11 -m venv ~/finetuning-env
source ~/finetuning-env/bin/activate
echo "✅ Ambiente virtual criado"
echo ""

# 4. Instalar PyTorch com CUDA
echo "🔥 Instalando PyTorch com CUDA 12.1..."
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
echo "✅ PyTorch instalado"
echo ""

# 5. Instalar dependências de fine-tuning
echo "📚 Instalando dependências..."
pip install sentence-transformers==2.7.0
pip install pandas scikit-learn tqdm
echo "✅ Dependências instaladas"
echo ""

# 6. Verificar PyTorch + CUDA
echo "🧪 Testando PyTorch com CUDA..."
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"
echo ""

# 7. Criar diretórios
echo "📁 Criando estrutura de diretórios..."
mkdir -p ~/embeddings/{data/finetuning,models,results,scripts}
echo "✅ Diretórios criados"
echo ""

echo "================================================================================"
echo "✅ SETUP CONCLUÍDO!"
echo "================================================================================"
echo ""
echo "Próximos passos:"
echo ""
echo "1. Ativar ambiente virtual:"
echo "   source ~/finetuning-env/bin/activate"
echo ""
echo "2. Upload dataset do seu computador local:"
echo "   scp -r source/embeddings/data/finetuning/* lpmoraes@<IP>:~/embeddings/data/finetuning/"
echo ""
echo "3. Upload scripts:"
echo "   scp source/embeddings/scripts/finetune_model.py lpmoraes@<IP>:~/embeddings/scripts/"
echo "   scp source/embeddings/scripts/evaluate_finetuned.py lpmoraes@<IP>:~/embeddings/scripts/"
echo ""
echo "4. Executar fine-tuning:"
echo "   cd ~/embeddings"
echo "   python scripts/finetune_model.py --dataset fewshot --epochs 2 --batch-size 16"
echo ""
