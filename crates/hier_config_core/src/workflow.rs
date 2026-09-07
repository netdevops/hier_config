//! High-level workflow orchestration for network configuration remediation and rollback.

use crate::models::{Platform, TagRule};
use crate::remediation::config_to_get_to;
use crate::tree::{Tree, TreeError};
use std::borrow::Cow;

/// Errors that can occur during workflow execution.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkflowError {
    /// Raised when running and generated configurations use different drivers or platforms.
    DriverMismatch {
        running: Platform,
        generated: Platform,
    },
    /// An underlying tree operation error.
    Tree(TreeError),
}

impl std::fmt::Display for WorkflowError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::DriverMismatch { .. } => {
                write!(
                    f,
                    "The running and generated configs must use the same driver."
                )
            }
            Self::Tree(err) => write!(f, "{err}"),
        }
    }
}

impl std::error::Error for WorkflowError {}

impl From<TreeError> for WorkflowError {
    fn from(err: TreeError) -> Self {
        Self::Tree(err)
    }
}

/// Orchestrates comparing a running configuration against a target generated configuration
/// to produce minimal remediation and rollback command sets.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkflowRemediation<'a> {
    pub running_config: Cow<'a, Tree>,
    pub generated_config: Cow<'a, Tree>,
    remediation: Option<Tree>,
    rollback: Option<Tree>,
}

impl WorkflowRemediation<'static> {
    /// Creates a workflow from owned running and generated trees.
    ///
    /// # Errors
    /// Returns [`WorkflowError::DriverMismatch`] if the two trees have different platforms.
    ///
    /// # Example
    /// ```
    /// use hier_config_core::models::Platform;
    /// use hier_config_core::tree::Tree;
    /// use hier_config_core::workflow::WorkflowRemediation;
    ///
    /// let running = Tree::from_str(Platform::CiscoIos, "vlan 10").unwrap();
    /// let generated = Tree::from_str(Platform::CiscoIos, "vlan 20").unwrap();
    /// let mut workflow = WorkflowRemediation::new(running, generated).unwrap();
    ///
    /// let rem = workflow.remediation_config().unwrap();
    /// assert!(!rem.all_children_sorted(rem.root).is_empty());
    /// ```
    pub fn new(running_config: Tree, generated_config: Tree) -> Result<Self, WorkflowError> {
        if running_config.driver.platform != generated_config.driver.platform {
            return Err(WorkflowError::DriverMismatch {
                running: running_config.driver.platform,
                generated: generated_config.driver.platform,
            });
        }
        Ok(Self {
            running_config: Cow::Owned(running_config),
            generated_config: Cow::Owned(generated_config),
            remediation: None,
            rollback: None,
        })
    }

    /// Creates a workflow by parsing running and generated configuration strings
    /// using the default driver for `platform`.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if either configuration fails to parse.
    ///
    /// # Example
    /// ```
    /// use hier_config_core::models::Platform;
    /// use hier_config_core::workflow::WorkflowRemediation;
    ///
    /// let mut workflow = WorkflowRemediation::from_strings(
    ///     Platform::CiscoIos,
    ///     "hostname router1\ninterface GigabitEthernet0/1\n  shutdown",
    ///     "hostname router1\ninterface GigabitEthernet0/1\n  no shutdown",
    /// ).unwrap();
    ///
    /// let rem_text = workflow.remediation_text(&[], &[]).unwrap();
    /// assert_eq!(rem_text, "interface GigabitEthernet0/1\n  no shutdown");
    /// ```
    pub fn from_strings(
        platform: Platform,
        running_text: &str,
        generated_text: &str,
    ) -> Result<Self, WorkflowError> {
        let running_config = Tree::from_str(platform, running_text)?;
        let generated_config = Tree::from_str(platform, generated_text)?;
        Self::new(running_config, generated_config)
    }
}

impl<'a> WorkflowRemediation<'a> {
    /// Creates a workflow by borrowing running and generated trees without cloning them.
    ///
    /// # Errors
    /// Returns [`WorkflowError::DriverMismatch`] if the two trees have different platforms.
    pub fn from_borrowed(
        running_config: &'a Tree,
        generated_config: &'a Tree,
    ) -> Result<Self, WorkflowError> {
        if running_config.driver.platform != generated_config.driver.platform {
            return Err(WorkflowError::DriverMismatch {
                running: running_config.driver.platform,
                generated: generated_config.driver.platform,
            });
        }
        Ok(Self {
            running_config: Cow::Borrowed(running_config),
            generated_config: Cow::Borrowed(generated_config),
            remediation: None,
            rollback: None,
        })
    }

    /// Returns a reference to the remediation configuration, computing it lazily on first access.
    ///
    /// The remediation configuration brings the device from running to generated state.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if diff computation fails.
    ///
    /// # Panics
    /// Panics if the internal remediation state is unexpectedly uninitialized after computation.
    pub fn remediation_config(&mut self) -> Result<&Tree, WorkflowError> {
        if self.remediation.is_none() {
            let mut rem = config_to_get_to(&self.running_config, &self.generated_config)?;
            rem.set_order_weight();
            self.remediation = Some(rem);
        }
        Ok(self.remediation.as_ref().expect("remediation initialized"))
    }

    /// Returns a mutable reference to the remediation configuration, computing it lazily on first access.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if diff computation fails.
    ///
    /// # Panics
    /// Panics if the internal remediation state is unexpectedly uninitialized after computation.
    pub fn remediation_config_mut(&mut self) -> Result<&mut Tree, WorkflowError> {
        if self.remediation.is_none() {
            let mut rem = config_to_get_to(&self.running_config, &self.generated_config)?;
            rem.set_order_weight();
            self.remediation = Some(rem);
        }
        Ok(self.remediation.as_mut().expect("remediation initialized"))
    }

    /// Returns a reference to the rollback configuration, computing it lazily on first access.
    ///
    /// The rollback configuration reverts the device from generated back to running state.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if diff computation fails.
    ///
    /// # Panics
    /// Panics if the internal rollback state is unexpectedly uninitialized after computation.
    pub fn rollback_config(&mut self) -> Result<&Tree, WorkflowError> {
        if self.rollback.is_none() {
            let mut roll = config_to_get_to(&self.generated_config, &self.running_config)?;
            roll.set_order_weight();
            self.rollback = Some(roll);
        }
        Ok(self.rollback.as_ref().expect("rollback initialized"))
    }

    /// Returns a mutable reference to the rollback configuration, computing it lazily on first access.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if diff computation fails.
    ///
    /// # Panics
    /// Panics if the internal rollback state is unexpectedly uninitialized after computation.
    pub fn rollback_config_mut(&mut self) -> Result<&mut Tree, WorkflowError> {
        if self.rollback.is_none() {
            let mut roll = config_to_get_to(&self.generated_config, &self.running_config)?;
            roll.set_order_weight();
            self.rollback = Some(roll);
        }
        Ok(self.rollback.as_mut().expect("rollback initialized"))
    }

    /// Applies tag rules to the remediation configuration.
    ///
    /// Computes the remediation configuration if it has not yet been computed.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if computing the remediation configuration fails.
    pub fn apply_remediation_tag_rules(
        &mut self,
        tag_rules: &[TagRule],
    ) -> Result<(), WorkflowError> {
        let rem = self.remediation_config_mut()?;
        rem.apply_tag_rules(tag_rules);
        Ok(())
    }

    /// Formats the remediation configuration as Cisco-style text filtered by tags.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if computing the remediation configuration fails.
    pub fn remediation_text(
        &mut self,
        include_tags: &[&str],
        exclude_tags: &[&str],
    ) -> Result<String, WorkflowError> {
        let rem = self.remediation_config()?;
        Ok(rem.rendered_text_by_tags(include_tags, exclude_tags))
    }

    /// Formats the rollback configuration as Cisco-style text filtered by tags.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if computing the rollback configuration fails.
    pub fn rollback_text(
        &mut self,
        include_tags: &[&str],
        exclude_tags: &[&str],
    ) -> Result<String, WorkflowError> {
        let roll = self.rollback_config()?;
        Ok(roll.rendered_text_by_tags(include_tags, exclude_tags))
    }

    /// Consumes and returns the remediation tree, computing it if necessary.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if computing the remediation configuration fails.
    pub fn take_remediation(&mut self) -> Result<Tree, WorkflowError> {
        if let Some(rem) = self.remediation.take() {
            Ok(rem)
        } else {
            let mut rem = config_to_get_to(&self.running_config, &self.generated_config)?;
            rem.set_order_weight();
            Ok(rem)
        }
    }

    /// Consumes and returns the rollback tree, computing it if necessary.
    ///
    /// # Errors
    /// Returns [`WorkflowError`] if computing the rollback configuration fails.
    pub fn take_rollback(&mut self) -> Result<Tree, WorkflowError> {
        if let Some(roll) = self.rollback.take() {
            Ok(roll)
        } else {
            let mut roll = config_to_get_to(&self.generated_config, &self.running_config)?;
            roll.set_order_weight();
            Ok(roll)
        }
    }
}
