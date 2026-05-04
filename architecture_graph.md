# Excel Automation Agent Architecture

This document contains a comprehensive architectural map of the entire system.

## High-Level System Architecture & Flow

```mermaid
graph TD
    classDef core fill:#4f46e5,stroke:#312e81,stroke-width:2px,color:#fff;
    classDef module fill:#0ea5e9,stroke:#0369a1,stroke-width:2px,color:#fff;
    classDef state fill:#f43f5e,stroke:#9f1239,stroke-width:2px,color:#fff;

    User((User Input)) --> Agent[Excel Agent]:::core

    subgraph Core & State
        Agent --> StateManager[State Manager]:::state
        StateManager --> EventBus[Event Bus]:::state
        StateManager -.-> AllModules
        EventBus -.-> AllModules
    end

    subgraph Perception
        Agent --> InputModule[Input Module]:::module
        Agent --> PerceptionModule[Perception Module]:::module
    end

    subgraph Intelligence
        Agent --> InterpreterModule[Interpreter Module]:::module
        Agent --> PlannerModule[Planner Module]:::module
    end

    subgraph Execution
        PlannerModule --> ExecutionPolicy[Execution Policy]:::module
        ExecutionPolicy --> ExecutorModule[Executor Module]:::module
        
        ExecutorModule --> DirectExecutor[Direct Executor]:::module
        ExecutorModule --> UIExecutor[UI Executor]:::module
        
        UIExecutor --> ScreenAnalyzer[Screen Analyzer]:::module
    end

    subgraph Feedback & Learning
        ExecutorModule --> VerifierModule[Verifier Module]:::module
        VerifierModule --> ReflectionModule[Reflection Module]:::module
        
        ReflectionModule --> MemoryManager[Memory Manager]:::module
        MemoryManager --> PlannerModule
    end
```

## Execution Flow (Detailed)

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant S as StateManager
    participant P as Planner
    participant E as Executor
    participant V as Verifier
    participant R as Reflection

    U->>A: Input task
    A->>S: Initialize state
    A->>P: Generate plan
    P->>A: Plan steps

    loop Execution Loop
        A->>E: Execute step
        E->>S: Update state
        E->>V: Validate output
        V->>A: Result

        alt Success
            A->>S: Continue
        else Failure
            A->>R: Analyze error
            R->>P: Replan / adjust
        end
    end

    A->>U: Final output
```

## Module Dependency (Final)

```mermaid
classDiagram
    class ExcelAgent {
        +run()
    }

    class StateManager {
        +get_state()
        +update()
    }

    class EventBus {
        +subscribe()
        +emit()
    }

    class ExecutionPolicy {
        +decide_mode()
    }

    class ExecutorModule {
        +execute_plan()
    }

    class ScreenAnalyzer {
        +compare_frames()
        +detect_text()
        +detect_popup()
    }

    class ReflectionModule {
        +classify_error()
        +decide_action()
    }

    ExcelAgent --> StateManager
    StateManager --> EventBus
    ExcelAgent --> ExecutionPolicy
    ExecutionPolicy --> ExecutorModule
    ExecutorModule --> ScreenAnalyzer
    ExecutorModule --> VerifierModule
    VerifierModule --> ReflectionModule
    ReflectionModule --> MemoryManager
```
