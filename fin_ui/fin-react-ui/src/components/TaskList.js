import React from 'react';
import { List, ListItem, ListItemText, ListItemSecondaryAction, IconButton, Chip, Typography, Stack } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';

export default function TaskList({ tasks, onUpdate }) {
  function handleEdit(task) {
    // For demo, just log. You can implement a dialog for editing.
    console.log('[TaskList Debug] Edit task:', task);
    // onUpdate(task._id, { status: 'completed' }); // Example usage
  }

  if (!tasks.length) return <Typography>No tasks found.</Typography>;

  return (
    <List>
      {tasks.map((task, idx) => (
        <ListItem key={task._id || idx} divider alignItems="flex-start">
          <ListItemText
            primary={<Stack direction="row" alignItems="center" spacing={2}>
              <span>{task.title}</span>
              <Chip label={task.status} color={task.status === 'completed' ? 'success' : (task.status === 'inprogress' ? 'info' : 'default')} size="small" />
              <Chip label={task.priority} color={task.priority === 'high' ? 'error' : (task.priority === 'low' ? 'default' : 'primary')} size="small" />
            </Stack>}
            secondary={<>
              <Typography variant="body2">{task.description}</Typography>
              <Typography variant="caption" color="text.secondary">Due: {task.end_date}</Typography>
            </>}
          />
          <ListItemSecondaryAction>
            <IconButton edge="end" aria-label="edit" onClick={() => handleEdit(task)}>
              <EditIcon />
            </IconButton>
          </ListItemSecondaryAction>
        </ListItem>
      ))}
    </List>
  );
}
