use nix::sys::resource::{setrlimit, Resource, Rlim};
use pyo3::prelude::*;
use pyo3::types::PyModule;
use regex::Regex;
use serde::Serialize;
use std::collections::HashMap;
use std::os::unix::process::CommandExt;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use tempfile::TempDir;

// ---------------------------------------------------------------------------
// Data structures
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
struct TestOutcome {
    name: String,
    status: String,
    message: String,
    duration_ms: u64,
}

#[derive(Serialize)]
struct ExecutionReport {
    exit_code: i32,
    stdout: String,
    stderr: String,
    tests: Vec<TestOutcome>,
    total_duration_ms: u64,
    timed_out: bool,
}

// ---------------------------------------------------------------------------
// Pytest output parser
// ---------------------------------------------------------------------------

fn parse_pytest_output(stdout: &str, stderr: &str) -> Vec<TestOutcome> {
    let mut tests: Vec<TestOutcome> = Vec::new();
    let combined = format!("{}\n{}", stdout, stderr);

    let re = Regex::new(r"(?m)^(\S+?)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)").unwrap();
    for cap in re.captures_iter(&combined) {
        tests.push(TestOutcome {
            name: format!("{}::{}", &cap[1], &cap[2]),
            status: cap[3].to_lowercase(),
            message: String::new(),
            duration_ms: 0,
        });
    }

    let block_re = Regex::new(r"(?s)_{3,}\s+(test\S+)\s+_{3,}\n(.*?)(?=_{3,}|\={3,}|\z)").unwrap();
    for cap in block_re.captures_iter(&combined) {
        let test_name = &cap[1];
        let block = &cap[2];

        let msg: String = block
            .lines()
            .filter(|l| l.starts_with("E ") || l.starts_with("E\t") || l.starts_with("> "))
            .map(|l| l.trim_start_matches("E ").trim_start_matches("E\t"))
            .collect::<Vec<_>>()
            .join("\n");

        if let Some(t) = tests.iter_mut().find(|t| t.name.ends_with(test_name)) {
            t.message = msg;
        }
    }

    if tests.is_empty() {
        let err_re = Regex::new(r"(?m)^ERROR\s+(.+?)\s*-").unwrap();
        for cap in err_re.captures_iter(&combined) {
            tests.push(TestOutcome {
                name: cap[1].to_string(),
                status: "error".to_string(),
                message: combined.chars().take(2000).collect(),
                duration_ms: 0,
            });
        }
    }

    if tests.is_empty() {
        let has_err = combined.contains("Error") || combined.contains("FAILED") || combined.contains("error");
        tests.push(TestOutcome {
            name: "execution".to_string(),
            status: if has_err { "error" } else { "unknown" }.to_string(),
            message: combined.chars().take(3000).collect(),
            duration_ms: 0,
        });
    }

    tests
}

// ---------------------------------------------------------------------------
// Timed child-process wait
// ---------------------------------------------------------------------------

enum RunOutcome {
    Completed(std::process::Output),
    TimedOut,
    SpawnError(String),
}

fn run_with_timeout(child: Result<Child, std::io::Error>, timeout: Duration) -> RunOutcome {
    let mut child = match child {
        Ok(c) => c,
        Err(e) => return RunOutcome::SpawnError(e.to_string()),
    };

    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => {
                return match child.wait_with_output() {
                    Ok(o) => RunOutcome::Completed(o),
                    Err(e) => RunOutcome::SpawnError(e.to_string()),
                };
            }
            Ok(None) => {
                if start.elapsed() >= timeout {
                    let _ = child.kill();
                    let _ = child.wait();
                    return RunOutcome::TimedOut;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => return RunOutcome::SpawnError(e.to_string()),
        }
    }
}

// ---------------------------------------------------------------------------
// Main entry point exposed to Python
// ---------------------------------------------------------------------------

#[pyfunction]
fn execute_sandbox(
    source_files: HashMap<String, String>,
    test_files: HashMap<String, String>,
    timeout_secs: u64,
    max_memory_mb: u64,
) -> PyResult<String> {
    let tmp = TempDir::new().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("tempdir creation failed: {}", e))
    })?;
    let root = tmp.path();

    for (name, content) in &source_files {
        let p = root.join(name);
        if let Some(parent) = p.parent() {
            std::fs::create_dir_all(parent).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("mkdir {}: {}", name, e))
            })?;
        }
        std::fs::write(&p, content).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("write {}: {}", name, e))
        })?;
    }

    for (name, content) in &test_files {
        let p = root.join(name);
        std::fs::write(&p, content).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("write {}: {}", name, e))
        })?;
    }

    let init = root.join("__init__.py");
    if !init.exists() {
        std::fs::write(&init, b"").map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("write __init__.py: {}", e))
        })?;
    }

    let test_names: Vec<&str> = test_files.keys().map(|s| s.as_str()).collect();
    let mut cmd = Command::new("python3");
    cmd.args(["-m", "pytest", "-v", "--tb=short", "--no-header"]);
    cmd.args(&test_names);
    cmd.current_dir(root);
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    // Scrub environment safely before forking
    cmd.env_clear();
    cmd.env("PATH", "/usr/local/bin:/usr/bin:/bin");
    cmd.env("PYTHONPATH", root.to_str().unwrap_or(""));
    cmd.env("HOME", root.to_str().unwrap_or("/tmp"));
    cmd.env("PYTHONDONTWRITEBYTECODE", "1");
    cmd.env("PYTHONUNBUFFERED", "1");
    cmd.env("LANG", "C.UTF-8");

    let mem = Rlim::from_raw(max_memory_mb * 1024 * 1024);
    let cpu = Rlim::from_raw(timeout_secs + 5);

    // SAFETY: The closures in pre_exec must only contain async-signal-safe operations.
    // setrlimit maps directly to safe C syscalls.
    unsafe {
        cmd.pre_exec(move || {
            let _ = setrlimit(Resource::RLIMIT_AS, mem, mem);
            let _ = setrlimit(Resource::RLIMIT_CPU, cpu, cpu);
            let _ = setrlimit(Resource::RLIMIT_NPROC, Rlim::from_raw(64), Rlim::from_raw(64));
            let _ = setrlimit(
                Resource::RLIMIT_FSIZE,
                Rlim::from_raw(10 * 1024 * 1024),
                Rlim::from_raw(10 * 1024 * 1024),
            );
            let _ = setrlimit(Resource::RLIMIT_CORE, Rlim::from_raw(0), Rlim::from_raw(0));
            let _ = setrlimit(
                Resource::RLIMIT_STACK,
                Rlim::from_raw(8 * 1024 * 1024),
                Rlim::from_raw(8 * 1024 * 1024),
            );
            Ok(())
        });
    }

    let start = Instant::now();
    let timeout = Duration::from_secs(timeout_secs);
    let outcome = run_with_timeout(cmd.spawn(), timeout);
    let elapsed_ms = start.elapsed().as_millis() as u64;

    let (stdout, stderr, exit_code, timed_out) = match outcome {
        RunOutcome::Completed(o) => (
            String::from_utf8_lossy(&o.stdout).to_string(),
            String::from_utf8_lossy(&o.stderr).to_string(),
            o.status.code().unwrap_or(-1),
            false,
        ),
        RunOutcome::TimedOut => (String::new(), "Execution timed out".to_string(), -1, true),
        RunOutcome::SpawnError(e) => (
            String::new(),
            format!("Failed to spawn process: {}. Is pytest installed?", e),
            -1,
            false,
        ),
    };

    let tests = parse_pytest_output(&stdout, &stderr);

    let report = ExecutionReport {
        exit_code,
        stdout,
        stderr,
        tests,
        total_duration_ms: elapsed_ms,
        timed_out,
    };

    serde_json::to_string(&report).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("JSON serialization failed: {}", e))
    })
}

#[pymodule]
fn forge_sandbox(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(execute_sandbox, m)?)?;
    Ok(())
}
