use serde::{Deserialize, Serialize};
use std::ops::{Index, IndexMut};

/// Generational identifier for a node in the arena.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct NodeId {
    pub index: u32,
    pub generation: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
enum Slot<T> {
    Occupied {
        generation: u32,
        value: T,
    },
    Vacant {
        generation: u32,
        next_free: Option<u32>,
    },
}

/// Converts a slot position into a [`NodeId`] index.
///
/// `NodeId::index` is a `u32`, so the arena can address at most `u32::MAX` slots.
/// Every slot position originates from [`Arena::insert`], which refuses to grow
/// past that bound, so this conversion cannot fail.
#[inline]
fn slot_index(idx: usize) -> u32 {
    u32::try_from(idx).expect("arena slot index exceeds u32::MAX")
}

/// A generational arena allocator that provides O(1) allocation, O(1) deallocation,
/// and safe generational index validation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Arena<T> {
    slots: Vec<Slot<T>>,
    free_head: Option<u32>,
    len: usize,
}

impl<T> Default for Arena<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T> Arena<T> {
    /// Creates an empty Arena.
    pub const fn new() -> Self {
        Self {
            slots: Vec::new(),
            free_head: None,
            len: 0,
        }
    }

    /// Creates an empty Arena with pre-allocated capacity.
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            slots: Vec::with_capacity(capacity),
            free_head: None,
            len: 0,
        }
    }

    /// Reserves room for at least `additional` more values.
    pub fn reserve(&mut self, additional: usize) {
        self.slots.reserve(additional);
    }

    /// Number of active items in the arena.
    pub const fn len(&self) -> usize {
        self.len
    }

    /// Returns true if the arena contains no active items.
    pub const fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// Allocates a new value in the arena and returns its `NodeId`.
    ///
    /// # Panics
    ///
    /// Panics if the arena would grow beyond `u32::MAX` slots, since `NodeId::index`
    /// is a `u32` and silently wrapping would alias live node ids.
    pub fn insert(&mut self, value: T) -> NodeId {
        self.len += 1;
        if let Some(free_idx) = self.free_head {
            let slot = &mut self.slots[free_idx as usize];
            match slot {
                Slot::Vacant {
                    generation,
                    next_free,
                } => {
                    let new_gen = generation.wrapping_add(1).max(1);
                    self.free_head = *next_free;
                    let id = NodeId {
                        index: free_idx,
                        generation: new_gen,
                    };
                    *slot = Slot::Occupied {
                        generation: new_gen,
                        value,
                    };
                    id
                }
                Slot::Occupied { .. } => unreachable!("free_head pointed to an occupied slot"),
            }
        } else {
            assert!(
                self.slots.len() < u32::MAX as usize,
                "arena capacity exhausted: NodeId::index is a u32"
            );
            let index = slot_index(self.slots.len());
            let generation = 1;
            self.slots.push(Slot::Occupied { generation, value });
            NodeId { index, generation }
        }
    }

    /// Checks if a `NodeId` is valid and refers to an active value.
    pub fn contains(&self, id: NodeId) -> bool {
        match self.slots.get(id.index as usize) {
            Some(Slot::Occupied { generation, .. }) => *generation == id.generation,
            _ => false,
        }
    }

    /// Retrieves an immutable reference to the value associated with `id`.
    pub fn get(&self, id: NodeId) -> Option<&T> {
        match self.slots.get(id.index as usize) {
            Some(Slot::Occupied { generation, value }) if *generation == id.generation => {
                Some(value)
            }
            _ => None,
        }
    }

    /// Retrieves a mutable reference to the value associated with `id`.
    pub fn get_mut(&mut self, id: NodeId) -> Option<&mut T> {
        match self.slots.get_mut(id.index as usize) {
            Some(Slot::Occupied { generation, value }) if *generation == id.generation => {
                Some(value)
            }
            _ => None,
        }
    }

    /// Removes a value by its `NodeId`, returning it if found.
    pub fn remove(&mut self, id: NodeId) -> Option<T> {
        let slot = self.slots.get_mut(id.index as usize)?;
        match slot {
            Slot::Occupied { generation, .. } if *generation == id.generation => {
                let old_gen = *generation;
                let next_free = self.free_head;
                self.free_head = Some(id.index);
                self.len -= 1;
                let new_slot = Slot::Vacant {
                    generation: old_gen,
                    next_free,
                };
                let old_slot = std::mem::replace(slot, new_slot);
                match old_slot {
                    Slot::Occupied { value, .. } => Some(value),
                    Slot::Vacant { .. } => unreachable!(),
                }
            }
            _ => None,
        }
    }

    /// Clears all entries from the arena.
    pub fn clear(&mut self) {
        self.slots.clear();
        self.free_head = None;
        self.len = 0;
    }

    /// Iterates over all active (`NodeId`, &T) pairs.
    pub fn iter(&self) -> impl Iterator<Item = (NodeId, &T)> {
        self.slots
            .iter()
            .enumerate()
            .filter_map(|(idx, slot)| match slot {
                Slot::Occupied { generation, value } => Some((
                    NodeId {
                        index: slot_index(idx),
                        generation: *generation,
                    },
                    value,
                )),
                Slot::Vacant { .. } => None,
            })
    }

    /// Iterates over all active (`NodeId`, &mut T) pairs.
    pub fn iter_mut(&mut self) -> impl Iterator<Item = (NodeId, &mut T)> {
        self.slots
            .iter_mut()
            .enumerate()
            .filter_map(|(idx, slot)| match slot {
                Slot::Occupied { generation, value } => Some((
                    NodeId {
                        index: slot_index(idx),
                        generation: *generation,
                    },
                    value,
                )),
                Slot::Vacant { .. } => None,
            })
    }
}

impl<T> Index<NodeId> for Arena<T> {
    type Output = T;

    fn index(&self, id: NodeId) -> &Self::Output {
        self.get(id)
            .unwrap_or_else(|| panic!("invalid NodeId in Arena::index: {id:?}"))
    }
}

impl<T> IndexMut<NodeId> for Arena<T> {
    fn index_mut(&mut self, id: NodeId) -> &mut Self::Output {
        self.get_mut(id)
            .unwrap_or_else(|| panic!("invalid NodeId in Arena::index_mut: {id:?}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arena_insert_get_remove() {
        let mut arena = Arena::new();
        assert!(arena.is_empty());
        let id1 = arena.insert("hello".to_string());
        let id2 = arena.insert("world".to_string());
        assert_eq!(arena.len(), 2);
        assert_eq!(arena.get(id1), Some(&"hello".to_string()));
        assert_eq!(arena.get(id2), Some(&"world".to_string()));

        let removed = arena.remove(id1);
        assert_eq!(removed, Some("hello".to_string()));
        assert_eq!(arena.len(), 1);
        assert_eq!(arena.get(id1), None);
        assert!(!arena.contains(id1));

        // Reusing slot increments generation
        let id3 = arena.insert("rust".to_string());
        assert_eq!(id3.index, id1.index);
        assert_ne!(id3.generation, id1.generation);
        assert_eq!(arena.get(id1), None);
        assert_eq!(arena.get(id3), Some(&"rust".to_string()));
    }
}
