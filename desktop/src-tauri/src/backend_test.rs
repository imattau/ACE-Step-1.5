//! Focused tests for backend launch primitives.

use crate::backend::{launch_secret, reserve_port};

#[test]
fn launch_secrets_are_random_hex_values() {
    let first = launch_secret().expect("first secret");
    let second = launch_secret().expect("second secret");
    assert_eq!(first.len(), 64);
    assert_ne!(first, second);
    assert!(first.chars().all(|character| character.is_ascii_hexdigit()));
}

#[test]
fn reserved_port_is_nonzero() {
    assert_ne!(reserve_port().expect("loopback port"), 0);
}
