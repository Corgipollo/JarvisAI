@echo off
REM ============================================================================
REM IMPORT_GUI_ODYSSEY.bat - Descarga 7,735 skills LISTAS desde HuggingFace
REM
REM Importa el dataset OpenGVLab/GUI-Odyssey y convierte cada episodio a
REM skill JSON en C:\Jarvis\data\skill_library\gui_odyssey_*.json
REM
REM Tiempo: 5-15 min (depende de internet, ~2GB descarga)
REM ============================================================================

title Importing GUI-Odyssey dataset

set JARVIS_DIR=C:\Jarvis
cd /d %JARVIS_DIR%

echo ============================================================================
echo                  IMPORT GUI-ODYSSEY (7,735 skills LISTAS)
echo ============================================================================
echo.

echo [1/3] Verificando huggingface_hub + datasets...
python -m pip install --quiet --upgrade huggingface_hub datasets
echo OK
echo.

echo [2/3] Descargando dataset (puede tardar 5-15 min)...
python -c "from datasets import load_dataset; ds = load_dataset('OpenGVLab/GUI-Odyssey'); print('Splits:', list(ds.keys())); print('Total train:', len(ds.get('train', [])))" 2>&1

echo.
echo [3/3] Convirtiendo a skill_library JSONs...
python -c "import json, os; from datasets import load_dataset; sd = r'%JARVIS_DIR%\data\skill_library'; os.makedirs(sd, exist_ok=True); ds = load_dataset('OpenGVLab/GUI-Odyssey', split='train'); print(f'Convirtiendo {len(ds)} episodios...'); n=0;
[open(os.path.join(sd, f'gui_odyssey_{i:05d}.json'), 'w', encoding='utf-8').write(json.dumps({'id': f'gui_odyssey_{i:05d}', 'name': ep.get('task', f'task_{i}'), 'steps': ep.get('steps', []), 'source': 'GUI-Odyssey', 'confidence': 0.5}, ensure_ascii=False)) for i, ep in enumerate(ds)]; print('OK importado')"

echo.
echo ============================================================================
echo                  RESULTADO
echo ============================================================================
echo.
dir C:\Jarvis\data\skill_library\gui_odyssey_*.json /b | find /c "."
echo skills importadas desde GUI-Odyssey
echo.
pause
