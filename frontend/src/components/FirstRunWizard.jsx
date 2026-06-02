/**
 * First Run Wizard — Componente React para guiar al usuario en su primer uso
 * Autor: Emmanuel Pedraza (@Corgipollo)
 * Fecha: 2026-05-31
 */

import React, { useState, useEffect } from 'react';
import './FirstRunWizard.css';

const FirstRunWizard = ({ onClose }) => {
  const [step, setStep] = useState('welcome'); // welcome, select_case, tutorial, completed
  const [useCases, setUseCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [tutorial, setTutorial] = useState(null);
  const [currentTutorialStep, setCurrentTutorialStep] = useState(0);
  const [integrations, setIntegrations] = useState({});

  // Cargar casos de uso disponibles al montar
  useEffect(() => {
    fetchAvailableUseCases();
  }, []);

  const fetchAvailableUseCases = async () => {
    try {
      const response = await fetch('http://localhost:8000/wizard/integrations');
      const data = await response.json();
      setIntegrations(data.integrations);
      setUseCases(data.use_cases);
    } catch (error) {
      console.error('Error cargando casos de uso:', error);
    }
  };

  const fetchTutorial = async (caseId) => {
    try {
      const response = await fetch(`http://localhost:8000/wizard/tutorial/${caseId}`);
      const data = await response.json();
      setTutorial(data);
      setCurrentTutorialStep(0);
      setStep('tutorial');
    } catch (error) {
      console.error('Error cargando tutorial:', error);
    }
  };

  const markCaseCompleted = async (caseId) => {
    try {
      await fetch(`http://localhost:8000/wizard/complete/${caseId}`, {
        method: 'POST'
      });
    } catch (error) {
      console.error('Error marcando caso como completado:', error);
    }
  };

  const finishWizard = async () => {
    try {
      await fetch('http://localhost:8000/wizard/finish', {
        method: 'POST'
      });
      setStep('completed');
      setTimeout(() => onClose(), 3000); // Cerrar después de 3 segundos
    } catch (error) {
      console.error('Error finalizando wizard:', error);
    }
  };

  const handleCaseSelect = (useCase) => {
    setSelectedCase(useCase);
    fetchTutorial(useCase.id);
  };

  const handleTutorialNext = () => {
    if (currentTutorialStep < tutorial.steps.length - 1) {
      setCurrentTutorialStep(currentTutorialStep + 1);
    } else {
      // Tutorial completado
      markCaseCompleted(selectedCase.id);
      setStep('select_case'); // Volver a selección para probar otro caso
    }
  };

  const handleTutorialPrevious = () => {
    if (currentTutorialStep > 0) {
      setCurrentTutorialStep(currentTutorialStep - 1);
    }
  };

  const handleSkip = () => {
    finishWizard();
  };

  // ===================================================================
  // RENDER: Pantalla de Bienvenida
  // ===================================================================
  if (step === 'welcome') {
    return (
      <div className="wizard-overlay">
        <div className="wizard-modal">
          <div className="wizard-header">
            <h1>🎉 ¡Bienvenido a Jarvis AI!</h1>
          </div>
          <div className="wizard-content">
            <p className="wizard-intro">
              Tu asistente personal voice-first está listo.
            </p>
            <p className="wizard-intro">
              ¿Qué quieres probar primero? Te guiaré paso a paso.
            </p>

            {/* Mostrar integraciones detectadas */}
            <div className="integrations-status">
              <h3>Integraciones Detectadas:</h3>
              <ul>
                <li className={integrations.gemini ? 'available' : 'unavailable'}>
                  {integrations.gemini ? '✓' : '✗'} Gemini API
                </li>
                <li className={integrations.spotify ? 'available' : 'unavailable'}>
                  {integrations.spotify ? '✓' : '✗'} Spotify
                </li>
                <li className={integrations.obsidian ? 'available' : 'unavailable'}>
                  {integrations.obsidian ? '✓' : '✗'} Obsidian Vault
                </li>
                <li className={integrations.ollama ? 'available' : 'unavailable'}>
                  {integrations.ollama ? '✓' : '✗'} Ollama (offline)
                </li>
              </ul>
            </div>
          </div>
          <div className="wizard-actions">
            <button className="btn-primary" onClick={() => setStep('select_case')}>
              Empezar Tutorial
            </button>
            <button className="btn-secondary" onClick={handleSkip}>
              Saltar (Ya sé usar Jarvis)
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===================================================================
  // RENDER: Selección de Caso de Uso
  // ===================================================================
  if (step === 'select_case') {
    return (
      <div className="wizard-overlay">
        <div className="wizard-modal">
          <div className="wizard-header">
            <h2>¿Qué quieres probar?</h2>
          </div>
          <div className="wizard-content">
            <div className="use-cases-grid">
              {useCases.map(useCase => (
                <div
                  key={useCase.id}
                  className={`use-case-card ${useCase.recommended ? 'recommended' : ''}`}
                  onClick={() => handleCaseSelect(useCase)}
                >
                  {useCase.recommended && <span className="badge">Recomendado</span>}
                  <h3>{useCase.name}</h3>
                  <p>{useCase.description}</p>
                  <div className="use-case-meta">
                    <span className="difficulty">{useCase.difficulty}</span>
                    <span className="time">{useCase.time_minutes} min</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="wizard-actions">
            <button className="btn-secondary" onClick={handleSkip}>
              Terminar Tutorial
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===================================================================
  // RENDER: Tutorial Paso a Paso
  // ===================================================================
  if (step === 'tutorial' && tutorial) {
    const currentStep = tutorial.steps[currentTutorialStep];
    const isLastStep = currentTutorialStep === tutorial.steps.length - 1;

    return (
      <div className="wizard-overlay">
        <div className="wizard-modal tutorial">
          <div className="wizard-header">
            <h2>{tutorial.title}</h2>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${((currentTutorialStep + 1) / tutorial.steps.length) * 100}%`
                }}
              />
            </div>
          </div>
          <div className="wizard-content">
            <div className="tutorial-step">
              <h3>
                Paso {currentStep.step} de {tutorial.steps.length}: {currentStep.title}
              </h3>
              <p className="step-description">{currentStep.description}</p>

              {currentStep.example_command && (
                <div className="command-example">
                  <h4>Comando de ejemplo:</h4>
                  <code>"{currentStep.example_command}"</code>
                </div>
              )}

              {currentStep.action_required && (
                <div className="action-required">
                  <p>⏸️ Prueba el comando ahora, luego haz clic en "Siguiente"</p>
                </div>
              )}
            </div>

            {isLastStep && (
              <div className="expected-result">
                <h4>Resultado Esperado:</h4>
                <p>{tutorial.expected_result}</p>
              </div>
            )}
          </div>
          <div className="wizard-actions">
            <button
              className="btn-secondary"
              onClick={handleTutorialPrevious}
              disabled={currentTutorialStep === 0}
            >
              ← Anterior
            </button>
            <button
              className="btn-primary"
              onClick={handleTutorialNext}
            >
              {isLastStep ? '✓ Completar' : 'Siguiente →'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ===================================================================
  // RENDER: Completado
  // ===================================================================
  if (step === 'completed') {
    return (
      <div className="wizard-overlay">
        <div className="wizard-modal completed">
          <div className="wizard-header">
            <h1>🎉 ¡Tutorial Completado!</h1>
          </div>
          <div className="wizard-content">
            <p className="success-message">
              Ya sabes usar Jarvis. Explora más casos de uso o empieza a trabajar.
            </p>
            <div className="next-steps">
              <h3>Próximos Pasos:</h3>
              <ul>
                <li>Configura más integraciones (Obsidian, Ollama)</li>
                <li>Personaliza comandos en <code>backend/integrations/</code></li>
                <li>Lee la documentación completa en <code>README.md</code></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default FirstRunWizard;
